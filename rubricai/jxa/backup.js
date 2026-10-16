// Write every card to one vCard file. Read-only on Contacts.
// usage: osascript -l JavaScript backup.js <out.vcf>
// Restore: double-click the .vcf, or File > Import in Contacts.app.
ObjC.import('Foundation');

function run(argv) {
  const cards = Application('Contacts').people.vcard();
  const text = cards.join('');
  $.NSString.alloc.initWithUTF8String(text).writeToFileAtomicallyEncodingError(argv[0], true, 4, null);
  return `backed up ${cards.length} cards`;
}
