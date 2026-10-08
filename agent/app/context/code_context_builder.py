"""Code Context assembly from a Java PR context (Phase 6.7.3).

Turns the PrContext DTO returned by GET /api/tasks/{taskId}/pr-context
into the existing CodeContext contract, reusing the Phase 6.1 to 6.5 steps
unchanged:

    parse_patch -> build_file_context -> attach_method_contexts
    -> attach_class_contexts -> attach_related_code

Assembly only: no budget is applied, no prompt is built and nothing is
sent anywhere. Files keep the Java order. A file whose content Java could
not read stays a FileContext with content_available=False, its reason kept
in content.error (when a content object is attached) and in notes, with an
empty method / class / related set, while the diff level information is
still produced from the patch. No code is ever fabricated.
"""

from app.context.class_context_builder import attach_class_contexts
from app.context.diff_parser import parse_patch
from app.context.file_context_builder import build_file_context
from app.context.method_context_builder import attach_method_contexts
from app.context.related_code_builder import attach_related_code
from app.schemas.code_context import CodeContext, FileContent, FileContext
from app.schemas.pr_context import PrContext, PrContextFile


class CodeContextBuilder:
    """Assembles the existing CodeContext models from one PrContext.

    base_sha stays None on purpose: the Java contract exposes only the base
    branch ref, never a base commit sha, and a ref name must not be stored
    as a sha. head_sha is the reviewed commit (PrContext.commitSha). Title,
    state and refs are not duplicated here; callers that need them keep the
    PrContext alongside the CodeContext.
    """

    def build(self, pr_context: PrContext) -> CodeContext:
        """Build one CodeContext from one PrContext, preserving file order."""
        files = [
            self._build_file(pr_context, pr_file)
            for pr_file in pr_context.files
        ]
        return CodeContext(
            repository=f"{pr_context.owner}/{pr_context.repo}",
            pr_number=pr_context.prNumber,
            base_sha=None,
            head_sha=pr_context.commitSha,
            files=files,
        )

    def _build_file(self, pr_context: PrContext,
                    pr_file: PrContextFile) -> FileContext:
        file_diff = parse_patch(
            path=pr_file.path,
            patch=pr_file.patch,
            status=pr_file.status,
            previous_path=pr_file.previousPath,
        )
        content = FileContent(
            path=pr_file.path,
            revision=pr_context.commitSha,
            content=pr_file.content,
            error=pr_file.content_reason,
        )

        file_context = build_file_context(file_diff, content)
        file_context = attach_method_contexts(file_context)
        file_context = attach_class_contexts(file_context)
        return attach_related_code(file_context)