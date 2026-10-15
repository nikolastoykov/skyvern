from __future__ import annotations

from pathlib import Path


ROOT = Path("/app")


def patch_once(path: Path, *, marker: str, old: str, new: str) -> None:
    text = path.read_text()

    if marker in text:
        print(f"Already patched: {path} ({marker})")
        return

    if old not in text:
        raise RuntimeError(
            f"Expected patch target not found in {path}. "
            "Upstream Skyvern probably changed; review the patch before rebuilding."
        )

    path.write_text(text.replace(old, new, 1))
    print(f"Patched: {path} ({marker})")


def patch_deepseek_openai_compatible() -> None:
    path = ROOT / "skyvern/forge/sdk/api/llm/config_registry.py"
    marker = "NIKOLA_DEEPSEEK_DISABLE_THINKING"

    old = '''        litellm_params = LiteLLMParams(
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            api_base=settings.OPENAI_COMPATIBLE_API_BASE,
            api_version=settings.OPENAI_COMPATIBLE_API_VERSION,
            model_info={"model_name": f"openai/{openai_compatible_model_name}"},
        )
'''

    new = '''        litellm_params = LiteLLMParams(
            api_key=settings.OPENAI_COMPATIBLE_API_KEY,
            api_base=settings.OPENAI_COMPATIBLE_API_BASE,
            api_version=settings.OPENAI_COMPATIBLE_API_VERSION,
            model_info={"model_name": f"openai/{openai_compatible_model_name}"},
        )

        # NIKOLA_DEEPSEEK_DISABLE_THINKING
        # DeepSeek's OpenAI-compatible endpoint otherwise emits reasoning_content
        # in tool loops. Keep this personal fork's DeepSeek configuration in
        # non-thinking mode while leaving other OpenAI-compatible models alone.
        if openai_compatible_model_name.lower().startswith("deepseek"):
            litellm_params["extra_body"] = {"thinking": {"type": "disabled"}}
'''

    patch_once(path, marker=marker, old=old, new=new)


def patch_uploaded_file_original_filename() -> None:
    path = ROOT / "skyvern/forge/sdk/api/files.py"

    marker_1 = "NIKOLA_PRESERVE_UPLOAD_ORIGINAL_FILENAME_LOOKUP"
    old_1 = '''    url = await uploaded_file_id_for_local_uri(url, organization_id) or url
    names_uploaded_file = is_uploaded_file_id(url)
    if names_uploaded_file:
        url = await resolve_uploaded_file_id(url, organization_id)
'''

    new_1 = '''    url = await uploaded_file_id_for_local_uri(url, organization_id) or url
    names_uploaded_file = is_uploaded_file_id(url)

    # NIKOLA_PRESERVE_UPLOAD_ORIGINAL_FILENAME_LOOKUP
    # Uploaded objects intentionally have a unique file_id_ prefix in storage to
    # prevent collisions. Remember the client-visible filename separately so the
    # browser/ATS receives the real resume filename instead of the storage key.
    uploaded_original_filename: str | None = None

    if names_uploaded_file:
        uploaded_file_id = url.strip()
        if organization_id is None:
            raise PermissionError(f"No permission to access file: {uploaded_file_id}")

        uploaded_record = await app.DATABASE.uploaded_files.get_uploaded_file(
            file_id=uploaded_file_id,
            organization_id=organization_id,
        )
        if uploaded_record is not None and uploaded_record.filename:
            uploaded_original_filename = sanitize_filename(os.path.basename(uploaded_record.filename))

        url = await resolve_uploaded_file_id(uploaded_file_id, organization_id)
'''

    patch_once(path, marker=marker_1, old=old_1, new=new_1)

    marker_2 = "NIKOLA_PRESERVE_UPLOAD_ORIGINAL_FILENAME_STAGE"
    old_2 = '''            filename = unquote(parsed.path.rsplit("/", 1)[-1]) if parsed.scheme == "file" else url.split("/")[-1]
'''

    new_2 = '''            # NIKOLA_PRESERVE_UPLOAD_ORIGINAL_FILENAME_STAGE
            storage_filename = (
                unquote(parsed.path.rsplit("/", 1)[-1])
                if parsed.scheme == "file"
                else url.split("/")[-1]
            )
            filename = uploaded_original_filename or storage_filename
'''

    patch_once(path, marker=marker_2, old=old_2, new=new_2)


def main() -> None:
    patch_deepseek_openai_compatible()
    patch_uploaded_file_original_filename()
    print("Nikola Skyvern patches applied successfully.")


if __name__ == "__main__":
    main()
