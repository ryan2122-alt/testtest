from pathlib import Path

from jarvis.tools.files import build_file_tools
from jarvis.tools.paths import PathNotAllowedError, resolve_within_allowed


def _tools_dict(allowed_dirs):
    return {tool.name: tool.handler for tool in build_file_tools(allowed_dirs)}


def test_resolve_within_allowed_accepts_descendant(tmp_path):
    allowed = (tmp_path,)
    sub = tmp_path / "notes.txt"
    resolved = resolve_within_allowed(str(sub), allowed)
    assert resolved == sub.resolve()


def test_resolve_within_allowed_rejects_outside_path(tmp_path):
    allowed = (tmp_path / "allowed",)
    (tmp_path / "allowed").mkdir()
    outside = tmp_path / "outside" / "secret.txt"

    import pytest

    with pytest.raises(PathNotAllowedError):
        resolve_within_allowed(str(outside), allowed)


def test_resolve_within_allowed_rejects_traversal_escape(tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    escape = str(allowed_root / ".." / "outside.txt")

    import pytest

    with pytest.raises(PathNotAllowedError):
        resolve_within_allowed(escape, (allowed_root,))


def test_resolve_within_allowed_rejects_symlink_escape(tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    outside_target = tmp_path / "outside"
    outside_target.mkdir()
    (outside_target / "secret.txt").write_text("top secret")

    link = allowed_root / "escape_link"
    link.symlink_to(outside_target)

    import pytest

    with pytest.raises(PathNotAllowedError):
        resolve_within_allowed(str(link / "secret.txt"), (allowed_root,))


def test_create_list_and_delete_file_within_allowed_dir(tmp_path):
    tools = _tools_dict((tmp_path,))

    result = tools["create_file"](path=str(tmp_path / "todo.txt"), content="buy milk")
    assert result.ok
    assert (tmp_path / "todo.txt").read_text() == "buy milk"

    listing = tools["list_files"](directory=str(tmp_path))
    assert listing.ok
    assert "todo.txt" in listing.content

    deleted = tools["delete_file"](path=str(tmp_path / "todo.txt"))
    assert deleted.ok
    assert not (tmp_path / "todo.txt").exists()


def test_create_file_outside_allowed_dir_is_refused(tmp_path):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    tools = _tools_dict((allowed_root,))

    result = tools["create_file"](path=str(tmp_path / "outside.txt"), content="x")

    assert not result.ok
    assert "Refused" in result.content
    assert not (tmp_path / "outside.txt").exists()


def test_move_and_rename_file(tmp_path):
    tools = _tools_dict((tmp_path,))
    tools["create_file"](path=str(tmp_path / "a.txt"), content="hi")

    moved = tools["move_file"](source=str(tmp_path / "a.txt"), destination=str(tmp_path / "sub" / "a.txt"))
    assert moved.ok
    assert (tmp_path / "sub" / "a.txt").exists()

    renamed = tools["rename_file"](path=str(tmp_path / "sub" / "a.txt"), new_name="b.txt")
    assert renamed.ok
    assert (tmp_path / "sub" / "b.txt").exists()


def test_delete_nonexistent_file_reports_failure(tmp_path):
    tools = _tools_dict((tmp_path,))
    result = tools["delete_file"](path=str(tmp_path / "ghost.txt"))
    assert not result.ok


def test_search_files_glob(tmp_path):
    tools = _tools_dict((tmp_path,))
    (tmp_path / "a.pdf").write_text("x")
    (tmp_path / "b.txt").write_text("x")

    result = tools["search_files"](directory=str(tmp_path), pattern="*.pdf")

    assert result.ok
    assert "a.pdf" in result.content
    assert "b.txt" not in result.content
