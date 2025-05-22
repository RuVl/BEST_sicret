from fluent.runtime import FluentLocalization, FluentResourceLoader

from env import ProjectKeys


def get_fluent_localization() -> FluentLocalization:
	"""
	Load locales
	:return: FluentLocalization object
	"""

	# Checks to make sure there's the correct file in the correct directory
	locale_dir = ProjectKeys.LOCALE_DIR

	# Validate path
	for locale in ProjectKeys.AVAILABLE_LOCALES:
		lang_dir = locale_dir / locale
		if not lang_dir.exists():
			raise FileNotFoundError(f"{lang_dir} directory not found")
		if not lang_dir.is_dir():
			raise NotADirectoryError(f"{lang_dir} is not a directory")

	# Add prefix {locale} for language directory mapping
	locale_files_name = set(map(lambda f: '{locale}/' + f.name, locale_dir.rglob('*.ftl')))
	if not len(locale_files_name):
		raise FileNotFoundError('locale files are not found')

	# Create the necessary objects and return a FluentLocalization object
	l10n_loader = FluentResourceLoader(str(locale_dir.absolute()))
	return FluentLocalization(
		locales=ProjectKeys.AVAILABLE_LOCALES,
		resource_ids=locale_files_name,
		resource_loader=l10n_loader
	)
