// Apply a reviewed plan to Contacts.app.
// usage: osascript -l JavaScript apply.js <plan.json> <undo.vcf> <log.json>
//
// Before the first change to any card, its vCard is appended to <undo.vcf>, so every
// edited or deleted card can be re-imported. Ops (see rubrica/plan.py):
//   delete        {id}
//   merge         {keep, others[], aliases}   copy values into keep, then delete others
//   remove_values {id, phones[], emails[], urls[], addresses[]}
//   set           {id, fields{firstName,middleName,lastName,nickname,organization,jobTitle,note}}
//   add           {id, phones[{label,value}], emails[...], urls[...]}
//   create        {firstName,lastName,organization,company,note,phones[],emails[]}
// Elements are created with C.Email({...}) + push(); C.make() fails with -10002 here.
ObjC.import('Foundation');

const read = p => $.NSString.stringWithContentsOfFileEncodingError(p, 4, null).js;
const write = (p, t) => $.NSString.alloc.initWithUTF8String(t).writeToFileAtomicallyEncodingError(p, true, 4, null);
const digits = s => (s || '').replace(/\D/g, '').slice(-9);
const norm = s => (s || '').toLowerCase().replace(/[\s,.]+/g, ' ').trim();
const tokens = s => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .split(/[^a-z0-9]+/).filter(Boolean);
const redundant = (alias, primary) => {
  const p = tokens(primary);
  return tokens(alias).every(t => p.some(u => u.startsWith(t)));
};

function run(argv) {
  const plan = JSON.parse(read(argv[0]));
  const C = Application('Contacts');
  const undo = [], log = [], saved = new Set();
  const person = id => C.people.byId(id);
  const remember = p => {
    const id = p.id();
    if (!saved.has(id)) { saved.add(id); undo.push(p.vcard()); }
  };
  const ctor = { phones: 'Phone', emails: 'Email', urls: 'Url' };
  const keyOf = { phones: digits, emails: norm, urls: v => norm(v).replace(/^(https? )?(www )?/, '') };

  function addValues(p, field, items) {
    const have = new Set(p[field].value().map(keyOf[field]));
    const added = [];
    for (const it of items) {
      const k = keyOf[field](it.value);
      if (!k || have.has(k)) continue;
      p[field].push(C[ctor[field]]({ label: it.label || 'other', value: it.value }));
      have.add(k); added.push(it.value);
    }
    return added;
  }

  function merge(op) {
    const P = person(op.keep); remember(P);
    const entry = { op: 'merge', keep: P.name(), merged: [], added: [] };
    const aliases = [], extraNotes = [];
    let pImage = null; try { pImage = P.image(); } catch (e) {}
    for (const id of op.others) {
      const o = person(id); remember(o);
      for (const f of ['phones', 'emails', 'urls']) {
        const items = o[f]().map(x => ({ label: x.label(), value: x.value() }));
        entry.added.push(...addValues(P, f, items));
      }
      const haveAddr = new Set(P.addresses.formattedAddress().map(norm));
      for (const a of o.addresses()) {
        const f = norm(a.formattedAddress());
        if (!f || haveAddr.has(f)) continue;
        P.addresses.push(C.Address({ label: a.label() || 'home', street: a.street() || '', city: a.city() || '',
          zip: a.zip() || '', state: a.state() || '', country: a.country() || '' }));
        haveAddr.add(f); entry.added.push(a.formattedAddress().replace(/\n/g, ', '));
      }
      for (const [prop, label] of [['organization', 'Company'], ['jobTitle', 'Job title'], ['nickname', 'Nickname']]) {
        const v = o[prop](), pv = P[prop]();
        if (v && !pv) { P[prop] = v; entry.added.push(`${label}: ${v}`); }
        else if (v && pv && norm(v).replace(/ /g, '') !== norm(pv).replace(/ /g, '')) extraNotes.push(`${label}: ${v}`);
      }
      if (o.birthDate() && !P.birthDate()) { P.birthDate = o.birthDate(); entry.added.push('birthday'); }
      if (!pImage) { try { const im = o.image(); if (im) { P.image = im; pImage = im; entry.added.push('photo'); } } catch (e) {} }
      const on = o.note();
      if (on && !norm(P.note()).includes(norm(on))) extraNotes.push(on);
      const name = o.name();
      if (op.aliases !== false && name && !name.includes('@') && !redundant(name, P.name())) aliases.push(name);
      entry.merged.push(name);
      C.delete(o);
    }
    if (aliases.length) extraNotes.push('Also saved as: ' + [...new Set(aliases)].join(', '));
    if (extraNotes.length) P.note = [P.note() || '', ...extraNotes].filter(Boolean).join('\n');
    return entry;
  }

  function removeValues(op) {
    const p = person(op.id); remember(p);
    const removed = [];
    for (const f of ['phones', 'emails', 'urls']) {
      const drop = [...(op[f] || [])];
      const items = p[f]();
      for (let i = items.length - 1; i >= 0; i--) {
        const k = drop.indexOf(items[i].value());
        if (k >= 0) { drop.splice(k, 1); removed.push(items[i].value()); C.delete(items[i]); }
      }
    }
    const dropAddr = (op.addresses || []).map(norm);
    const addrs = p.addresses();
    for (let i = addrs.length - 1; i >= 0; i--) {
      const k = dropAddr.indexOf(norm(addrs[i].formattedAddress()));
      if (k >= 0) { dropAddr.splice(k, 1); removed.push(addrs[i].formattedAddress().replace(/\n/g, ', ')); C.delete(addrs[i]); }
    }
    return { op: 'remove_values', name: p.name(), removed };
  }

  function create(op) {
    const props = {};
    for (const k of ['firstName', 'lastName', 'organization', 'note']) if (op[k]) props[k] = op[k];
    const p = C.Person(props); C.people.push(p);
    if (op.company) p.company = true;
    addValues(p, 'phones', op.phones || []); addValues(p, 'emails', op.emails || []);
    return { op: 'create', name: p.name(), id: p.id() };
  }

  for (const op of plan.ops) {
    try {
      if (op.op === 'delete') { const p = person(op.id); remember(p); log.push({ op: 'delete', name: p.name() }); C.delete(p); }
      else if (op.op === 'merge') log.push(merge(op));
      else if (op.op === 'remove_values') log.push(removeValues(op));
      else if (op.op === 'set') { const p = person(op.id); remember(p); for (const k in op.fields) p[k] = op.fields[k]; log.push({ op: 'set', name: p.name(), fields: op.fields }); }
      else if (op.op === 'add') { const p = person(op.id); remember(p); const a = ['phones', 'emails', 'urls'].flatMap(f => addValues(p, f, op[f] || [])); log.push({ op: 'add', name: p.name(), added: a }); }
      else if (op.op === 'create') log.push(create(op));
      else log.push({ op: op.op, error: 'unknown op' });
    } catch (e) {
      log.push({ op: op.op, error: String(e), target: op.id || op.keep });
    }
  }
  write(argv[1], undo.join(''));   // before save: the undo file exists even if save fails
  C.save();
  write(argv[2], JSON.stringify(log, null, 1));
  const errors = log.filter(l => l.error).length;
  return `applied ${log.length - errors} ops, ${errors} errors, ${C.people.length} cards now; undo: ${argv[1]}`;
}
