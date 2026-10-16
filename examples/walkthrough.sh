#!/usr/bin/env bash
# The whole ladder on the invented demo address book, applied offline (Contacts.app is
# never touched). Regenerates examples/walkthrough.txt, which the README quotes.
#   bash examples/walkthrough.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/examples/make_demo.py" >/dev/null
W="$(mktemp -d)"
cp "$ROOT/examples/demo/contacts.json" "$W/"
cd "$W"
show() { local out="" a; for a in "$@"; do [[ "$a" == *" "* ]] && a="\"$a\""; out+=" $a"; done; echo "$out"; }
rb() { echo; echo "\$ rb$(show "$@")"; PYTHONPATH="$ROOT" python3 -m rubrica "$@"; }
yes_() { echo "  (user: yes)"; PYTHONPATH="$ROOT" python3 -m rubrica apply "$1" --offline contacts.json | sed 's/^/  /'; }

{
rb inventory
rb scan exact --plan p1.json;            yes_ p1.json
rb scan same-name --plan p2.json;        yes_ p2.json
rb scan linked --plan p3.json
echo "  (user: merge the three groups; Nora and Ivo are two people; omar@example.org is Omar's card)"
rb pick p3.json --merge "Omar Lanza" "omar@example.org"
yes_ p3.json
rb scan name-only --plan p4.json
echo "  (user: all five are the same person)"
rb pick p4.json --merge "Dad Dad Work" "Dad Tim" --merge "Gio" "Gio Casa" \
  --merge "Gabriella Gallo" "Gabri Gallo" --merge "Adrián Ruiz" "Adriàn Ruiz" \
  --merge "Ann Bell" "ann_bell@example.org"
yes_ p4.json
rb scan in-card --plan p5.json;          yes_ p5.json
rb mail --db "$ROOT/examples/demo/Envelope Index" --me you@example.org --years 3 --out mail.json
echo "  (user: add Sabine, the Hausverwaltung, Pietro Costa and Kim Lee; skip the club and Dora)"
python3 - <<'EOF'
import json
rows = {r["address"]: r for r in json.load(open("mail.json"))}
keep = [rows["s.weber@studio.example"], rows["pietro.costa@example.org"], rows["kim.lee@example.org"],
        dict(rows["hausverwaltung@flat.example"], company=True)]
json.dump(keep, open("mail.json", "w"))
EOF
rb add-plan mail.json --plan p6.json;    yes_ p6.json
rb whatsapp --folder "$ROOT/examples/demo/whatsapp"
echo "  (user: add Yara and the optician)"
echo '[{"name": "Yara (Swimming)", "phone": "+491525552525"},
       {"name": "Foto Ottica Sole", "company": true, "phone": "+393295552626"}]' > wa.json
rb add-plan wa.json --plan p7.json;      yes_ p7.json
rb scan title-case --plan p8.json;       yes_ p8.json
rb inventory
echo
echo "\$ # the merged Tommaso Ferri card"
python3 -c "
import json
c = next(c for c in json.load(open('contacts.json')) if c['name'] == 'Tommaso Ferri')
print(json.dumps({k: c[k] for k in ('name', 'phones', 'emails', 'note')}, indent=1, ensure_ascii=False))"
} 2>&1 | sed "s#$ROOT/##g; s#$W/##g" > "$ROOT/examples/walkthrough.txt"
rm -rf "$W"
echo "wrote examples/walkthrough.txt"
