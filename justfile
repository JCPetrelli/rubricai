# Rubricai: all commands run from the repo root. Working files go to ./work (git-ignored).

# Back up, export and print the inventory: the safe first step
run:
    mkdir -p work
    python3 -m rubricai backup --dir work/backups
    python3 -m rubricai export --out work/contacts.json
    python3 -m rubricai inventory --contacts work/contacts.json

# Build one plan: just scan exact|same-name|linked|name-only|in-card|title-case
scan KIND:
    mkdir -p work
    python3 -m rubricai export --out work/contacts.json
    python3 -m rubricai scan {{KIND}} --contacts work/contacts.json --plan work/plan-{{KIND}}.json

# Link the skill into ~/.claude/skills (manual install without the plugin system)
install:
    mkdir -p ~/.claude/skills
    ln -sfn "$(pwd)/skills/rubricai" ~/.claude/skills/rubricai
    @echo "Installed: ~/.claude/skills/rubricai -> $(pwd)/skills/rubricai"

test:
    python3 -m pytest -q

# Invented demo address book: all eight rungs offline -> examples/walkthrough.txt
demo:
    bash examples/walkthrough.sh
