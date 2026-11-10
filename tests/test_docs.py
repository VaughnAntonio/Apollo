from pathlib import Path

README = Path("README.md")
CARDS = [Path(f"docs/model-card-{n}.md") for n in ("regime", "range", "fractal")]
HEADINGS = ("Data", "Target", "Features", "Validation", "Metrics", "Failure modes", "Limitations")


def test_readme_has_the_essentials():
    text = README.read_text()
    assert "Research tool. Not financial advice." in text
    assert "https://vaughnantonio.github.io/Apollo/" in text
    assert "TTrades" in text
    assert "```mermaid" in text
    for card in CARDS:
        assert f"]({card.as_posix()})" in text


def test_each_model_card_has_every_section():
    for card in CARDS:
        headings = {line.removeprefix("## ").strip() for line in card.read_text().splitlines() if line.startswith("## ")}
        assert set(HEADINGS) <= headings, card


def test_docs_use_no_dashes():
    for doc in [README, *CARDS, Path("docs/media/architecture.md")]:
        assert "—" not in doc.read_text(), doc
