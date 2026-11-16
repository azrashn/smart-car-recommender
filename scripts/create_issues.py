"""Plan tablosundaki görevleri GitHub Issues'a aktarır.

Gereksinim: GitHub CLI (https://cli.github.com) kurulu ve `gh auth login` yapılmış olmalı.

Kullanım:
    python scripts/create_issues.py --dry-run      # önce ne yapılacağını göster
    python scripts/create_issues.py                # label, milestone ve issue'ları oluştur

Önce aşağıdaki MEMBERS sözlüğüne ekip üyelerinin GitHub kullanıcı adlarını yazın.
Boş bırakılan üyeler için issue atanmadan (assignee olmadan) açılır.
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

REPO = "azrashn/smart-car-recommender"

# ÜYE → GitHub kullanıcı adı (doldurun)
MEMBERS = {
    "UYE1": "Belisozcelik",  # M1 Araç verisi ve katalog
    "UYE2": "fatihoguzkaya",  # M2 Tercih girişi ve i18n
    "UYE3": "karya-karya",  # M3 Öneri motoru
    "UYE4": "orhancardak",  # M4 AI katmanı
    "UYE5": "SudeKarakoc1",  # M5 Karşılaştırma, maliyet, sonuç UI
    "UYE6": "azrashn",  # M6 Scenario Lab ve QA
}

MILESTONES = {
    "Hafta 1 (16-22 Kas)": "2026-11-22T20:59:00Z",
    "Hafta 2 (23-29 Kas)": "2026-11-29T20:59:00Z",
    "Hafta 3 (30 Kas-6 Ara)": "2026-12-06T20:59:00Z",
    "Hafta 4 (7-13 Ara)": "2026-12-13T20:59:00Z",
}

LABELS = {
    **{f"module:M{i}": "1d76db" for i in range(1, 7)},
    "type:code": "0e8a16",
    "type:docs": "fbca04",
    "type:test": "5319e7",
    "type:data": "c5def5",
    "type:bug": "d73a4a",
    "priority:P0": "b60205",
    "priority:P1": "d93f0b",
    "priority:P2": "fef2c0",
    "idea": "ededed",
}


def run(cmd, dry):
    print("$", " ".join(cmd) if len(" ".join(cmd)) < 160 else " ".join(cmd)[:160] + " …")
    if dry:
        return ""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("  ! ", res.stderr.strip())
    return res.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--csv", default=str(Path(__file__).with_name("issues.csv")))
    args = ap.parse_args()
    dry = args.dry_run

    for name, color in LABELS.items():
        run(["gh", "label", "create", name, "--color", color, "--force", "-R", REPO], dry)

    existing = set()
    if not dry:
        out = run(["gh", "api", f"repos/{REPO}/milestones?state=all&per_page=100"], dry)
        existing = {m["title"] for m in json.loads(out or "[]")}
    for title, due in MILESTONES.items():
        if title not in existing:
            run(["gh", "api", f"repos/{REPO}/milestones", "-f", f"title={title}", "-f", f"due_on={due}"], dry)

    with open(args.csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        cmd = ["gh", "issue", "create", "-R", REPO, "--title", r["title"], "--body", r["body"],
               "--milestone", r["milestone"]]
        for lab in r["labels"].split(","):
            cmd += ["--label", lab]
        user = MEMBERS.get(r["assignee"], "")
        if user:
            cmd += ["--assignee", user]
        run(cmd, dry)
    print(f"\n{len(rows)} issue {'oluşturulacak (dry-run)' if dry else 'oluşturuldu'}.")


if __name__ == "__main__":
    sys.exit(main())
