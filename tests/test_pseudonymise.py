from chama.anonymisation.pseudonymise import (
    member_code,
    normalise_name,
    pseudonymise_column,
    resolve_name,
)

KEY = b"test-key-only"


def test_normalise_ignores_case_dots_and_spaces():
    assert normalise_name("  J. Kamau ") == normalise_name("j kamau")


def test_same_name_gives_same_code_every_time():
    assert member_code("John Kamau", "chama_a", KEY) == member_code("john  kamau", "chama_a", KEY)


def test_different_chamas_give_different_codes():
    assert member_code("John Kamau", "chama_a", KEY) != member_code("John Kamau", "chama_b", KEY)


def test_different_key_gives_different_code():
    assert member_code("John Kamau", "chama_a", KEY) != member_code("John Kamau", "chama_a", b"other")


def test_code_does_not_contain_the_name():
    code = member_code("John Kamau", "chama_a", KEY)
    assert "kamau" not in code.lower() and code.startswith("M-")


def test_aliases_merge_spellings_into_one_member():
    aliases = {"j kamau": "john kamau", "kamau j": "john kamau"}
    codes = pseudonymise_column(["J. Kamau", "Kamau J.", "John Kamau"], "chama_a", aliases, KEY)
    assert len(set(codes)) == 1


def test_unknown_name_is_left_for_review():
    assert resolve_name("Mary W.", {}) == "mary w"
