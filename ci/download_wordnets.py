"""Download/ensure all WordNets used by tests. Called by CI."""
import argparse
import os
import sys

sys.path.insert(0, "src")

parser = argparse.ArgumentParser(description="Download IntentLang WordNets")
parser.add_argument(
    "--data-dir",
    default=os.environ.get("WN_DATA_DIR"),
    help="Writable WordNet data directory (defaults to WN_DATA_DIR or wn's default)",
)
args = parser.parse_args()

if args.data_dir:
    os.environ["WN_DATA_DIR"] = args.data_dir

from intentlang import lexicon

for lang in ("es", "en", "zh", "ja", "ar", "fi", "he"):
    lexicon.ensure_installed(lang)
print("WordNets installed:", lexicon.supported_languages())
