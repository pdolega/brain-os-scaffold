#!/usr/bin/env python3
"""Deterministic half of AGENTS.md §5.3. Reads the vault, never writes.

Usage:  python3 tools/lint.py [--errors-only] [--quiet]
Exit 1 if any ERROR, else 0. WARN never fails the run.

Checks (mechanical only — judgment checks stay with the agent's /brain:lint):
  frontmatter parses (incl. strict-YAML quoting) · required fields per type · enum values · unknown fields ·
  list-vs-scalar · source_ids paths exist · wikilinks resolve · sensitivity
  inheritance (seeds/syntheses only) · rule-5 name scan in seed/synthesis/draft bodies · unclassified after
  ingest · sources not ingested after 7 days · stale needs_review · next_test past
  due · published seed without url · agenda counterpart/status/Outcome (§4.21) ·
  firehose lifecycle/stream/reference integrity ·
  sync.md vs canonical scan · log.md entry format · index.md coverage · <# #> instructions left in pages.
"""
import os, re, sys, glob, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
TODAY = dt.date.today()
ERRORS, WARNS = [], []
def err(f, m): ERRORS.append((f, m))
def warn(f, m): WARNS.append((f, m))

CANONICAL_LOG_OPS = {
    'sync', 'triage', 'radar', 'promote', 'retire', 'ingest', 'activity',
    'query', 'review', 'feedback', 'lint', 'audit', 'schema', 'correction',
    'capture', 'maintenance', 'human-instruction', 'draft', 'agenda',
}

# ---------- minimal YAML-ish frontmatter parser (scalars, inline lists, block lists) ----
def strip_comment(v):
    """Drop a trailing `# comment`, but never a `#` inside a quoted value."""
    v = v.strip()
    if v[:1] in ('"', "'"):
        close = v.find(v[0], 1)
        while v[0] == '"' and close > 0 and v[close-1] == '\\': close = v.find('"', close + 1)
        if close > 0: return v[:close+1]
        return v
    return re.sub(r'\s+#.*$', '', v).strip()

def pdate(v):
    """The YYYY-MM-DD prefix of v as a date, or None when it is not a real date."""
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', str(v or ''))
    if not m: return None
    try: return dt.date.fromisoformat(m.group(1))
    except ValueError: return None

def parse_fm(text):
    if not text.startswith('---'): return None, text
    end = text.find('\n---', 3)
    if end < 0: return None, text
    block, body = text[3:end], text[end+4:]
    fm, key = {}, None
    for line in block.split('\n'):
        if not line.strip() or line.lstrip().startswith('#'): continue
        if re.match(r'^\s+-\s', line) and key is not None:
            v = line.split('-', 1)[1].strip()
            v = strip_comment(v).strip('"').strip("'")
            fm.setdefault(key, [])
            if not isinstance(fm[key], list): fm[key] = []
            fm[key].append(v); continue
        m = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if not m: continue
        key, v = m.group(1), m.group(2)
        v = strip_comment(v)
        if v == '' : fm[key] = None
        elif v.startswith('[') and v.endswith(']'):
            inner = v[1:-1].strip()
            fm[key] = [x.strip().strip('"').strip("'") for x in re.split(r',(?![^\[]*\]\])', inner) if x.strip()] if inner else []
        else: fm[key] = v.strip('"').strip("'")
    return fm, body

def check_quoting(f, text):
    """Frontmatter must survive a STRICT YAML parser (Obsidian's js-yaml, PyYAML),
    not just parse_fm above. parse_fm is deliberately lenient — it strips outer
    quotes and would silently accept `title: "a "b" c"`, which strict YAML rejects,
    dropping the whole page out of the bases/ views. Catch that class here."""
    if not text.startswith('---'): return
    end = text.find('\n---', 3)
    if end < 0: return
    for line in text[3:end].split('\n'):
        m = re.match(r'^\s*([A-Za-z_][\w-]*):\s*(.+?)\s*$', line)
        if not m: continue
        k, v = m.group(1), strip_comment(m.group(2))
        if len(v) < 2 or v[0] not in '"\'': continue
        q = v[0]
        if not v.endswith(q):
            err(f, f'`{k}`: unterminated {q} in frontmatter — strict YAML rejects this line'); continue
        inner = v[1:-1].replace('\\"', '') if q == '"' else v[1:-1].replace("''", '')
        if q in inner:
            err(f, f'`{k}`: unescaped {q} inside a quoted value — strict YAML rejects this line '
                   f'(use the other quote style)')

# ---------- schema ------------------------------------------------------------------
COMMON = {'type','domain','sensitivity','bears_on','parent','aliases','created','updated',
          'source_ids','confidence','needs_review','tags','streams','item_ids','pattern_ids','outputs',
          'superseded_by'}
EXTRA = {
 'source': {'source','source_id','content_hash','captured','participants','title','author',
            'published','url','word_count','format','purpose','file','extraction','platform',
            'thread_id'},
 'voice-reference': {'source','source_id','content_hash','captured','participants','title','author',
            'published','url','word_count','format','purpose','role'},
 'daily': set(), 'review': set(), 'rollup': {'week'},
 'person': {'company'}, 'company': {'relationship'},
 'project': {'status','owner','due'}, 'concept': {'maturity'},
 'venture': {'status'}, 'initiative': {'status'}, 'topic': {'status'},
 'synthesis': {'question'}, 'product-idea': {'status','score','next_test'},
 'content-seed': {'status','audience','form','channel','published','url'},
 'question': {'status','owner','due'}, 'goal': set(), 'context': set(),
 'firehose-item': {'source','source_id','content_hash','captured','updated_at','status',
            'read_state','content_status','title','author','published','url','promoted_to'},
 'firehose-stream': {'stream','status'},
 'firehose-pattern': {'status','pattern_kind','first_seen','last_seen'},
 'firehose-radar': {'week'},
 'analytics': {'platform','month'},
 'draft': {'seed','status','form','channel','audience'},
 'agenda': {'counterpart','when','status'},
}
REQUIRED = {
 'source': {'type','source','source_id','content_hash','captured','domain','sensitivity','bears_on'},
 'voice-reference': {'type','source','domain','sensitivity'},
 'daily': {'type','domain','bears_on','created','source_ids'},
 'review': {'type','domain','created','source_ids'},
 'rollup': {'type','domain','created','week','source_ids'},
 'analytics': {'type','domain','platform','month','created','source_ids'},
 'draft': {'type','domain','seed','status','created','source_ids'},
 'agenda': {'type','domain','counterpart','status','sensitivity','created','source_ids'},
 'person': {'type','domain','sensitivity','company'},
 'company': {'type','domain','sensitivity','relationship'},
 'project': {'type','domain','parent','status','sensitivity'},
 'concept': {'type','domain','maturity','sensitivity','source_ids'},
 'venture': {'type','domain','status','confidence','sensitivity'},
 'initiative': {'type','domain','status','confidence','sensitivity'},
 'topic': {'type','domain','status','sensitivity'},
 'synthesis': {'type','domain','question','confidence','sensitivity'},
 'product-idea': {'type','domain','parent','status','score','next_test','sensitivity'},
 'content-seed': {'type','domain','status','audience','form','channel','parent','sensitivity'},
 'question': {'type','domain','status','owner','sensitivity'},
 'goal': {'type','domain'}, 'context': {'type','domain'},
 'firehose-item': {'type','domain','source','source_id','content_hash','captured','updated_at',
            'sensitivity','streams','status','read_state','content_status','title','tags'},
 'firehose-stream': {'type','stream','domain','status','sensitivity','created','updated'},
 'firehose-pattern': {'type','domain','streams','status','pattern_kind','first_seen','last_seen',
            'confidence','item_ids','outputs','created','updated','tags'},
 'firehose-radar': {'type','domain','streams','week','created','item_ids','pattern_ids'},
}
ENUM = {
 'domain': {'audience','work','research','none','unclassified'},   # + venture slugs, below
 'sensitivity': {'open','restricted'},
 'confidence': {'high','medium','low'},
 'maturity': {'seedling','developing','evergreen','contested'},
 'relationship': {'client','prospect','employer','vendor','competitor','other'},
 'form': {'short','long'},
 'read_state': {'unread','agent-read','human-read'},
 'content_status': {'complete','partial','metadata-only','unavailable'},
 'pattern_kind': {'mechanism','trend','opportunity','anomaly'},
}
STATUS = {
 'project': {'active','paused','done','abandoned'}, 'venture': {'exploring','active','paused','killed'},
 'initiative': {'active','paused','stopped'}, 'topic': {'exploring','synthesised','parked'},
 'product-idea': {'signal','hypothesis','validating','parked','killed'},
 'content-seed': {'captured','incubating','draft','approved','published','parked','archived'},
 'draft': {'outline','drafting','review','final','published'},
 'agenda': {'open','held','closed'},
 'question': {'open','closed'},
 'firehose-item': {'new','triaged','watching','promoted','ignored'},
 'firehose-stream': {'active','paused'},
 'firehose-pattern': {'emerging','supported','contested','promoted','stale'},
}
LISTS = {'bears_on','aliases','source_ids','tags','participants','channel','streams',
         'item_ids','pattern_ids','outputs','counterpart'}
SCALARS = {'domain','sensitivity','audience','form','status','type','parent','confidence',
           'source','source_id','read_state','content_status','pattern_kind','promoted_to','stream',
           'thread_id'}
HUMAN_OWNED = ('AGENTS.md','context/','goals/goals.md','bases/','Dashboard.md','config/',
               'firehose/streams/')
NULLABLE = {'company'}             # required key, may be left empty
SOURCE_KINDS = {'plaud','readwise','youtube','web','notes','attachments','my-writing',
                'substack','typefully','linkedin','email'}
KNOWN_BEARS = {'audience'}         # + venture, initiative and topic slugs, below
KNOWN_STREAMS = set()
INSTRUCTION_PATHS = ('journal/','wiki/','queues/','drafts/','goals/','context/',
                     'firehose/streams/','firehose/radar/','Dashboard.md')

# ---------- load pages --------------------------------------------------------------
pages = {}
for f in glob.glob('**/*.md', recursive=True):
    if f.startswith(('.obsidian/','.claude/','.github/','tools/')) or f in ('index.md','log.md','sync.md','CLAUDE.md','AGENTS.md'): continue
    if os.path.basename(f) == 'README.md': continue   # folder placeholders, not vault pages
    try: text = open(f, encoding='utf-8').read()
    except Exception as e: err(f, f'unreadable: {e}'); continue
    check_quoting(f, text)
    fm, body = parse_fm(text)
    pages[f] = (fm, body, text)

titles = {}
for f,(fm,body,text) in pages.items():
    titles[os.path.splitext(os.path.basename(f))[0]] = f
    if fm and isinstance(fm.get('aliases'), list):
        for a in fm['aliases']: titles.setdefault(a, f)
def slugs(d): return {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(d + '/*.md')
                      if os.path.basename(f) != 'README.md'}
VENTURES = slugs('wiki/ventures')
ENUM['domain'] |= VENTURES
KNOWN_BEARS |= VENTURES | slugs('wiki/initiatives') | slugs('wiki/topics')
# Audiences: the backticked slugs under `## Audiences` in context/self.md. None yet → unchecked.
if os.path.exists('context/self.md'):
    am = re.search(r'^## Audiences\s*\n(.*?)(?=\n## |\Z)', open('context/self.md', encoding='utf-8').read(), re.M | re.S)
    aud = {s for l in (am.group(1).splitlines() if am else []) if 'TODO' not in l and 'example' not in l
           for s in re.findall(r'^\s*-\s+\**`([a-z0-9-]+)`', l)}
    if aud: ENUM['audience'] = aud
for f,(fm,body,text) in pages.items():
    if fm and fm.get('type') == 'firehose-stream' and fm.get('stream'): KNOWN_STREAMS.add(fm['stream'])

def sens(f):
    fm = pages.get(f, (None,))[0]; return (fm or {}).get('sensitivity')
def resolve(link):
    name = link.split('|')[0].split('#')[0].strip().strip('"')
    name = name[:-3] if name.endswith('.md') else name
    if name + '.md' in pages: return name + '.md'
    return titles.get(os.path.basename(name)) or titles.get(name)

# ---------- per-page checks -----------------------------------------------------------
_log_text = open('log.md', encoding='utf-8').read() if os.path.exists('log.md') else ''
# Only `ingest` entries count — a sync/promote line mentioning a source_id must not
# mark the source as ingested (false "unclassified after ingest" otherwise).
ingested_titles = '\n'.join(l for l in _log_text.splitlines()
                            if re.match(r'^- \[\d{4}-\d{2}-\d{2}\] ingest \| ', l))
def sid_named_in(sid, text):
    """True if `text` names `sid`: the full id, or — for plaud/readwise only — an
    8-character id prefix (`plaud:2b570036…`). AGENTS.md §5.1 step 10."""
    if not sid: return False
    if sid in text: return True
    short = sid.split(':',1)[-1][:8]
    return sid.startswith(('plaud:','readwise:')) and (sid.split(':')[0]+':'+short) in text

def ingest_logged(fm):
    return sid_named_in((fm or {}).get('source_id') or '', ingested_titles)

for f,(fm,body,text) in pages.items():
    if any(f.startswith(h) for h in HUMAN_OWNED) and not f.startswith('goals/alignment/'):
        if fm and fm.get('needs_review') is not None: err(f, 'human-owned file carries needs_review')
        if not f.startswith('firehose/streams/'): continue
        if (fm or {}).get('type') != 'firehose-stream': err(f, 'page under firehose/streams/ is not type firehose-stream'); continue
    if fm is None: err(f, 'no frontmatter'); continue
    t = fm.get('type')
    if t not in REQUIRED: err(f, f'unknown or missing type: {t}'); continue
    for k in REQUIRED[t] - set(fm): err(f, f'missing required field `{k}`')
    for k in (REQUIRED[t] & set(fm)) - NULLABLE:
        if fm[k] is None or fm[k] == '': err(f, f'required field `{k}` is empty')
    if t in ('source','voice-reference') and fm.get('source') and fm['source'] not in SOURCE_KINDS:
        err(f, f'`source: {fm["source"]}` not in {sorted(SOURCE_KINDS)}')
    for k in set(fm) - COMMON - EXTRA[t]: err(f, f'field not in schema for {t}: `{k}`')
    for k,allowed in ENUM.items():
        v = fm.get(k)
        if v is not None and not isinstance(v, list) and v not in allowed: err(f, f'`{k}: {v}` not in {sorted(allowed)}')
    if t in STATUS and fm.get('status') not in STATUS[t]: err(f, f'`status: {fm.get("status")}` not in {sorted(STATUS[t])}')
    for k in LISTS:
        if k in fm and fm[k] is not None and not isinstance(fm[k], list): err(f, f'`{k}` must be a list')
    for k in SCALARS:
        if k in fm and isinstance(fm[k], list): err(f, f'`{k}` must be a scalar')
    if fm.get('domain') == 'unclassified' and t == 'source' and ingest_logged(fm): err(f, 'still domain: unclassified after ingest')
    if fm.get('domain') == 'unclassified' and t != 'source': err(f, '`unclassified` is legal only on un-ingested source pages')
    for b in fm.get('bears_on') or []:
        if b not in KNOWN_BEARS: err(f, f'bears_on `{b}` is not a dossier or topic')
    for s in fm.get('streams') or []:
        if s not in KNOWN_STREAMS: err(f, f'stream `{s}` has no registry page under firehose/streams/')
    # source_ids exist; inheritance
    restricted_src = None
    for sid in fm.get('source_ids') or []:
        if sid.startswith('[['):
            tgt = resolve(sid.strip('[]'))
            if not tgt: err(f, f'source_ids wikilink does not resolve: {sid}')
            elif tgt.startswith('firehose/'): err(f, f'firehose page is provisional and cannot be source_ids provenance: {sid}')
            elif (pages[tgt][0] or {}).get('type') == 'voice-reference': err(f, f'voice reference is imitated, never cited: {sid}')
            elif sens(tgt) == 'restricted' and (pages[tgt][0] or {}).get('type') != 'daily': restricted_src = restricted_src or sid
        else:
            if sid.startswith('firehose/'): err(f, f'firehose path is provisional and cannot be source_ids provenance: {sid}')
            elif not os.path.exists(sid): err(f, f'source_ids path missing: {sid}')
            elif sid not in pages: err(f, f'source_ids must point at a vault page or raw/ source: {sid}')
            elif (pages[sid][0] or {}).get('type') == 'voice-reference': err(f, f'voice reference is imitated, never cited: {sid}')
            elif sens(sid) == 'restricted': restricted_src = restricted_src or sid
    # provisional firehose references
    for item in fm.get('item_ids') or []:
        tgt = resolve(item.strip('[]')) if item.startswith('[[') else item
        if not tgt or not os.path.exists(tgt): err(f, f'item_ids path missing: {item}')
        elif ((pages.get(tgt) or (None,))[0] or {}).get('type') != 'firehose-item':
            err(f, f'item_ids target is not a firehose-item: {item}')
    for pattern in fm.get('pattern_ids') or []:
        tgt = resolve(pattern.strip('[]')) if pattern.startswith('[[') else pattern
        if not tgt or not os.path.exists(tgt): err(f, f'pattern_ids path missing: {pattern}')
        elif ((pages.get(tgt) or (None,))[0] or {}).get('type') != 'firehose-pattern':
            err(f, f'pattern_ids target is not a firehose-pattern: {pattern}')
    for output in fm.get('outputs') or []:
        tgt = resolve(output.strip('[]')) if output.startswith('[[') else output
        if not tgt or not os.path.exists(tgt): err(f, f'outputs target missing: {output}')
    if restricted_src and fm.get('sensitivity') == 'open' and t in ('content-seed','synthesis','draft'):
        err(f, f'sensitivity open but cites restricted {restricted_src}')
    # wikilinks resolve (body + fm)
    for link in set(re.findall(r'\[\[([^\]]+?)\]\]', text)):
        if not resolve(link): warn(f, f'unresolved wikilink [[{link}]]')
    # parent constraints
    par = fm.get('parent')
    if par:
        tgt = resolve(par.strip('[]'))
        if not tgt: err(f, f'parent does not resolve: {par}')
        else:
            pt = (pages[tgt][0] or {}).get('type')
            ok = {'project': {'venture','initiative'}, 'product-idea': {'venture','initiative'},
                  'content-seed': {'initiative','venture'}, 'concept': {'topic'}, 'question': {'venture','initiative','topic'},
                  'initiative': {'venture'}}.get(t, {'venture','initiative','topic'})
            if pt not in ok: err(f, f'parent type {pt} not allowed for {t}')
    if t == 'product-idea' and fm.get('domain') != 'audience' and not par: err(f, 'product idea without parent')
    if t == 'project' and not fm.get('due'): warn(f, 'project without due date (is it an initiative?)')
    # dates
    for k in ('created','updated','due','published','captured','updated_at','first_seen','last_seen','when'):
        v = fm.get(k)
        if v and not pdate(v): err(f, f'`{k}` not a valid ISO date: {v}')
    if t == 'product-idea':
        m = re.search(r'\d{4}-\d{2}-\d{2}', str(fm.get('next_test') or ''))
        nd = pdate(m.group(0)) if m else None
        if not nd: err(f, 'next_test has no valid date')
        elif nd < TODAY: warn(f, f'next_test date passed ({m.group(0)})')
        if re.search(r'^\| \*\*Total\*\* \| \*\*(\d+)\*\*', body, re.M):
            tot = int(re.search(r'^\| \*\*Total\*\* \| \*\*(\d+)\*\*', body, re.M).group(1))
            if str(tot) != str(fm.get('score')): err(f, f'score {fm.get("score")} != table total {tot}')
    if t == 'content-seed' and fm.get('status') == 'published' and not fm.get('url'): err(f, 'published seed without url')
    if t == 'question' and fm.get('status') == 'closed' and re.search(r'## Answer / resolution\s*\n\s*(Open\.?)?\s*$', body): err(f, 'closed question with no resolution')
    if t == 'agenda':
        # AGENTS.md §4.21 / §5.3: a human-facing pre-meeting artifact, closed by ingest + human.
        if not f.startswith('queues/agendas/'): err(f, 'agenda page outside queues/agendas/')
        cps = fm.get('counterpart') or []
        if not cps: err(f, 'agenda has no counterpart')
        for cp in cps:
            tgt = resolve(cp.strip('[]'))
            if not tgt or not tgt.startswith(('wiki/people/','wiki/companies/')):
                err(f, f'counterpart does not resolve to a person or company page: {cp}')
            elif sens(tgt) == 'restricted' and fm.get('sensitivity') == 'open':
                err(f, f'sensitivity open but counterpart {cp} is restricted')
        if fm.get('needs_review') in ('true', True): err(f, 'agenda carries needs_review (human-facing artifact)')
        outcome = re.search(r'^## Outcome[^\n]*\n(.*?)(?=\n## |\Z)', body, re.M | re.S)
        outcome_text = (outcome.group(1) if outcome else '').strip()
        st = fm.get('status')
        if st == 'held' and not any(str(x).startswith('raw/') or
                                    (str(x).startswith('[[') and (resolve(str(x).strip('[]')) or '').startswith('raw/'))
                                    for x in fm.get('source_ids') or []):
            err(f, 'held agenda with no raw/ source in source_ids')
        if st == 'closed' and not outcome_text: err(f, 'closed agenda with empty Outcome')
        if st == 'open' and pdate(fm.get('when')):
            age = (TODAY - pdate(fm['when'])).days
            if age > 7: warn(f, f'meeting not recorded: open agenda {age} days after `when`')
    if t == 'source' and fm.get('source') == 'email':
        # AGENTS.md §4.1 / §5.3: one immutable snapshot per thread; a continuation
        # page needs an earlier snapshot of the same thread to continue from.
        tid = fm.get('thread_id')
        if not tid: err(f, 'email source page missing thread_id')
        if fm.get('format') not in ('thread','continuation'):
            err(f, f'email format `{fm.get("format")}` not in thread/continuation')
        if fm.get('format') == 'continuation':
            cap = fm.get('captured') or ''
            earlier = [g for g,(gfm,_,_) in pages.items() if g != f and gfm
                       and gfm.get('source') == 'email' and gfm.get('thread_id') == tid
                       and (gfm.get('captured') or '') <= cap]
            if not earlier: err(f, f'continuation with no earlier snapshot of thread {tid}')
    if t == 'firehose-item':
        st, cs, rs, dest = fm.get('status'), fm.get('content_status'), fm.get('read_state'), fm.get('promoted_to')
        if fm.get('source') not in ('readwise','youtube','web'):
            err(f, f'firehose source `{fm.get("source")}` not in readwise/youtube/web')
        if st == 'promoted':
            if cs != 'complete': err(f, f'promoted firehose item has content_status: {cs}, expected complete')
            if not dest: err(f, 'promoted firehose item missing promoted_to')
            elif not os.path.exists(dest): err(f, f'promoted_to path missing: {dest}')
            else:
                dfm = (pages.get(dest) or (None,))[0] or {}
                if dfm.get('type') != 'source': err(f, f'promoted_to is not a raw source: {dest}')
                if dfm.get('source_id') != fm.get('source_id'): err(f, f'promoted_to source_id differs: {dest}')
        elif dest: err(f, f'status {st} carries promoted_to; only promoted items may')
        if st in ('triaged','watching','promoted') and rs not in ('agent-read','human-read'):
            err(f, f'status {st} requires read_state agent-read or human-read')
        if st in ('triaged','watching','promoted') and not (fm.get('streams') or []):
            err(f, f'status {st} requires at least one stream')
        if st == 'new' and pdate(fm.get('captured')):
            age = (TODAY - pdate(fm['captured'])).days
            if age > 7: warn(f, f'firehose item untriaged for {age} days')
    if t == 'firehose-pattern':
        if not (fm.get('item_ids') or []): err(f, 'firehose pattern has no item_ids')
        for heading in ('Source independence','Evidence against'):
            sec = re.search(r'^## ' + re.escape(heading) + r'\s*\n(.*?)(?=\n## |\Z)', body, re.M | re.S)
            if not sec or not sec.group(1).strip(): err(f, f'{heading} is empty')
        if fm.get('status') == 'promoted' and not (fm.get('outputs') or []):
            err(f, 'promoted firehose pattern has no outputs')
    if fm.get('needs_review') in ('true', True) and pdate(fm.get('created')):
        age = (TODAY - pdate(fm['created'])).days
        if age > 14: warn(f, f'needs_review for {age} days')
    if t == 'source' and pdate(fm.get('captured')) and '/activity/' not in f and not ingest_logged(fm):
        age = (TODAY - pdate(fm['captured'])).days
        if age > 7: warn(f, f'not ingested after {age} days')
    if t in ('concept','venture','initiative','topic'):
        sec = re.search(r'## Evidence (against|of drift)[^\n]*\n(.*?)(?=\n## |\Z)', body, re.S)
        if not sec: err(f, 'missing the mandatory Evidence against / of drift section')
        elif not sec.group(2).strip(): err(f, 'Evidence against / of drift is empty (write "Not yet examined." if you have nothing)')
    if t == 'draft' and not resolve(str(fm.get('seed') or '').strip('"').strip('[]')):
        err(f, f'draft seed does not resolve: {fm.get("seed")}')
    # Only pages the human edits carry executable markers (AGENTS.md §6 Trust boundary);
    # code spans and fences are documentation, never instructions.
    if f.startswith(INSTRUCTION_PATHS):
        prose = re.sub(r'`[^`\n]*`', '', re.sub(r'```.*?```', '', body, flags=re.S))
        if '<#' in prose: warn(f, 'contains a <# … #> instruction awaiting execution')

# ---------- stable external identity --------------------------------------------------
by_source_id = {}
for f,(fm,body,text) in pages.items():
    sid = (fm or {}).get('source_id')
    if sid: by_source_id.setdefault(sid, []).append(f)
for sid, files in by_source_id.items():
    if len(files) < 2: continue
    raw_files = [f for f in files if f.startswith('raw/')]
    firehose_files = [f for f in files if f.startswith('firehose/')]
    valid_pair = (len(files) == 2 and len(raw_files) == 1 and len(firehose_files) == 1 and
                  (pages[firehose_files[0]][0] or {}).get('status') == 'promoted' and
                  (pages[firehose_files[0]][0] or {}).get('promoted_to') == raw_files[0])
    if not valid_pair:
        for f in files: err(f, f'duplicate source_id `{sid}` outside a valid promoted firehose → raw pair')

# ---------- rule 5 name scan -----------------------------------------------------------
names = set()
for f,(fm,body,text) in pages.items():
    if not fm: continue
    if f.startswith('wiki/people/') or (f.startswith('wiki/companies/') and fm.get('relationship') == 'client'):
        names.add(os.path.splitext(os.path.basename(f))[0])
        for a in fm.get('aliases') or []: names.add(a)
names = {n for n in names if len(n) >= 2}
for f,(fm,body,text) in pages.items():
    if fm and fm.get('type') in ('content-seed','synthesis','draft'):
        for n in sorted(names):
            if re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', body):
                err(f, f'rule 5: names `{n}` in body')

# ---------- voice: banned phrases (context/voice.md fenced `banned` block) --------------
if os.path.exists('context/voice.md'):
    vm = re.search(r'```banned\n(.*?)```', open('context/voice.md', encoding='utf-8').read(), re.S)
    banned = [l.strip() for l in (vm.group(1).splitlines() if vm else []) if l.strip()]
    for f,(fm,body,text) in pages.items():
        # published text is frozen; rules added later must not fail it
        if fm and fm.get('type') in ('draft','content-seed') and fm.get('status') != 'published':
            # ignore the Sources / Revision log tail of a draft
            core = re.split(r'\n## (Sources|Revision log)\b', body)[0]
            for b in banned:
                if re.search(r'(?<!\w)' + re.escape(b) + r'(?!\w)', core, re.I):
                    err(f, f'voice: banned phrase `{b}` in body')

# ---------- vault-level checks ---------------------------------------------------------
if os.path.exists('log.md'):
    log_text = open('log.md', encoding='utf-8').read()
    log_lines = log_text.splitlines()
    header = log_text.split('\n- [', 1)[0]
    for op in sorted(CANONICAL_LOG_OPS):
        if f'`{op}`' not in header:
            err('log.md', f'header omits canonical operation `{op}`')

    parsed_entries = []
    for i, line in enumerate(log_lines, 1):
        if line.startswith('## ['):
            err('log.md', f'line {i}: heading-style entry; use `- [date] …`')
        if not line.startswith('- ['):
            continue
        m = re.match(r'^- \[(\d{4}-\d{2}-\d{2})\] ([^|]+?) \| ([^|]+?) \| (.+)$', line)
        if not m:
            err('log.md', f'line {i}: malformed entry; expected `- [date] operation | subject | detail`')
            continue
        date_s, op, subject, detail = (x.strip() for x in m.groups())
        try:
            dt.date.fromisoformat(date_s)
        except ValueError:
            err('log.md', f'line {i}: invalid date `{date_s}`')
        parsed_entries.append((i, op, subject, detail))

    for i, op, subject, detail in parsed_entries:
        if op not in CANONICAL_LOG_OPS:
            err('log.md', f'line {i}: operation `{op}` is not a canonical operation')

    # Every ingest entry must NAME its source (§5.1 step 10). `ingest_logged` above can
    # only find a source by `source_id`, so a title-only entry marks its source
    # un-ingested forever and silently disables the `unclassified after ingest` check.
    # Same matcher in both directions, so the two can never disagree.
    known_sids = [ (pages[f][0] or {}).get('source_id') for f in pages
                   if f.startswith('raw/') and (pages[f][0] or {}).get('type') == 'source' ]
    known_sids = [s for s in known_sids if s]
    for i, op, subject, detail in parsed_entries:
        if op != 'ingest' or subject in ('batch summary', ''): continue
        line = log_lines[i-1]
        if not any(sid_named_in(s, line) for s in known_sids):
            err('log.md', f'line {i}: ingest entry names no resolvable source_id '
                          f'(subject `{subject[:40]}`) — §5.1 step 10')
idx = open('index.md', encoding='utf-8').read() if os.path.exists('index.md') else ''
for f in pages:
    if (pages[f][0] or {}).get('type') == 'agenda' and (pages[f][0] or {}).get('status') == 'closed': continue
    if f.startswith(('wiki/','queues/')) and os.path.splitext(os.path.basename(f))[0] not in idx:
        warn(f, 'not listed in index.md')
# sync.md vs canonical scan (Plaud and email on raw/captured; Readwise on firehose/updated_at)
if os.path.exists('sync.md'):
    sm = open('sync.md', encoding='utf-8').read()
    for src in ('plaud','readwise','email'):
        row = re.search(r'^\| ' + src + r' \| (\S+) \|', sm, re.M)
        field = 'updated_at' if src == 'readwise' else 'captured'
        caps = [ (pages[f][0] or {}).get(field) for f in pages
                 if pages[f][0] and
                 ((src == 'plaud' and f.startswith('raw/') and '/plaud/' in f) or
                  (src == 'email' and f.startswith('raw/') and '/email/' in f) or
                  (src == 'readwise' and f.startswith('firehose/') and '/readwise/' in f)) ]
        caps = [c for c in caps if c]
        wm = row.group(1) if row else None
        if wm and caps and wm not in ('—','-') and max(str(c) for c in caps)[:len(wm)] > wm:
            err('sync.md', f'{src} watermark {wm} behind canonical max {field} {max(caps)}')

# Basename collisions. Obsidian resolves `[[name]]` by basename (`newLinkFormat:
# shortest`, so links are written bare), and the `titles` map above is last-wins —
# two pages with the same filename make every short link to either of them
# ambiguous, and silently send `source_ids` resolution to the wrong page.
# Historical instance: journal/YYYY-MM-DD.md (Daily Log) vs
# journal/reviews/YYYY-MM-DD.md (Daily Review), fixed by the `review-` prefix.
by_base = {}
for f in pages:
    by_base.setdefault(os.path.splitext(os.path.basename(f))[0], []).append(f)
for base, fs in sorted(by_base.items()):
    if len(fs) > 1:
        for f in sorted(fs):
            err(f, f'basename collision: [[{base}]] is ambiguous across {", ".join(sorted(fs))}')

# Non-ASCII basenames under people/ and companies/ (§3): the
# filename is the ASCII transliteration; the original spelling lives in `aliases`.
for f in pages:
    if f.startswith(('wiki/people/', 'wiki/companies/')):
        base = os.path.splitext(os.path.basename(f))[0]
        if not base.isascii():
            err(f, f'non-ASCII filename: transliterate to ASCII and keep "{base}" as an alias')

# ---------- report ---------------------------------------------------------------------
quiet = '--quiet' in sys.argv; eo = '--errors-only' in sys.argv
print(f'lint {TODAY}: {len(ERRORS)} errors, {len(WARNS)} warnings, {len(pages)} pages')
for f,m in ERRORS: print(f'ERROR {f}: {m}')
if not eo:
    for f,m in WARNS: print(f'WARN  {f}: {m}')
sys.exit(1 if ERRORS else 0)
