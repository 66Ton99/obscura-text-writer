"""EDIT-LOOP: a run request without an edit pass limit takes it from the editor settings of the story."""
from ..run_models import RunRequest

DEFAULT_LIMIT = 5


def resolve_edit_pass_limit(repo, request: RunRequest) -> RunRequest:
    """The same request when it carries a limit, else a copy with the editor's limit (5 without an editor role)."""
    if request.edit_pass_limit is not None:
        return request
    from ..authoring.blueprints import get_role_settings
    editor = get_role_settings(repo, request.story_id).get('editor')
    return request.model_copy(update={'edit_pass_limit': editor.edit_pass_limit if editor else DEFAULT_LIMIT})
