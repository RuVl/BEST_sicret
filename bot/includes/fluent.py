from pathlib import Path

from fluent.runtime import FluentLocalization, FluentResourceLoader


def get_fluent_localization() -> FluentLocalization:
    """
    Load locales file 'locale.ftl; from 'l10n' directory
    :return: FluentLocalization object
    """

    # Checks to make sure there's the correct file in the correct directory
    locale_dir = Path(__file__).parent.parent.joinpath("l10n")
    if not locale_dir.exists():
        raise FileNotFoundError("'l10n' directory not found")

    if not locale_dir.is_dir():
        raise NotADirectoryError("'l10n' is not a directory")

    locale_file = Path(locale_dir, "locale.ftl")
    if not locale_file.exists():
        raise FileNotFoundError("locale.txt file not found")

    # Create the necessary objects and return a FluentLocalization object
    l10n_loader = FluentResourceLoader(str(locale_file.absolute()))
    return FluentLocalization(
        locales=["ru"],
        resource_ids=[str(locale_file.absolute())],
        resource_loader=l10n_loader
    )