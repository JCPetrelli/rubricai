// Export every card as JSON. Read-only.
// usage: osascript -l JavaScript export.js <out.json> [images]
// Bulk property reads (people.name(), people.phones.value() ...) take about a second for
// thousands of cards. Images cannot be read in bulk (error -1741), so they are optional
// and read one card at a time.
ObjC.import('Foundation');

function write(path, text) {
  $.NSString.alloc.initWithUTF8String(text).writeToFileAtomicallyEncodingError(path, true, 4, null);
}

function run(argv) {
  const C = Application('Contacts');
  const p = C.people;
  const ids = p.id(), n = ids.length;
  const col = {
    name: p.name(), first: p.firstName(), middle: p.middleName(), last: p.lastName(),
    nickname: p.nickname(), company: p.company(), organization: p.organization(),
    job: p.jobTitle(), note: p.note(), birthday: p.birthDate(), modified: p.modificationDate(),
    phoneValues: p.phones.value(), phoneLabels: p.phones.label(),
    emailValues: p.emails.value(), emailLabels: p.emails.label(),
    urlValues: p.urls.value(), urlLabels: p.urls.label(),
    addrValues: p.addresses.formattedAddress(), addrLabels: p.addresses.label(),
  };
  const pairs = (vals, labels) => vals.map((v, i) => ({ label: labels[i] || '', value: v }));
  const iso = d => (d ? d.toISOString() : null);
  const out = [];
  for (let i = 0; i < n; i++) {
    const c = {
      id: ids[i], name: col.name[i] || '', first: col.first[i] || '', middle: col.middle[i] || '',
      last: col.last[i] || '', nickname: col.nickname[i] || '', company: !!col.company[i],
      organization: col.organization[i] || '', job: col.job[i] || '', note: col.note[i] || '',
      birthday: iso(col.birthday[i]), modified: iso(col.modified[i]),
      phones: pairs(col.phoneValues[i], col.phoneLabels[i]),
      emails: pairs(col.emailValues[i], col.emailLabels[i]),
      urls: pairs(col.urlValues[i], col.urlLabels[i]),
      addresses: col.addrValues[i].map((v, k) => ({ label: col.addrLabels[i][k] || '', formatted: v || '' })),
    };
    if (argv[1] === 'images') {
      try { c.has_image = !!p.byId(ids[i]).image(); } catch (e) { c.has_image = false; }
    }
    out.push(c);
  }
  write(argv[0], JSON.stringify(out));
  return `exported ${n} cards`;
}
