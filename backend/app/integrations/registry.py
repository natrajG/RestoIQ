from app.integrations.base_provider import IntegrationProvider


class IntegrationRegistry:
    """Explicit allow-list of adapters. Adding a provider = write an adapter and call register()."""
    _providers: dict[str, IntegrationProvider] = {}

    @classmethod
    def register(cls, provider: IntegrationProvider) -> IntegrationProvider:
        slug = provider.info.slug
        if slug in cls._providers:
            raise ValueError(f"Provider {slug} already registered")
        cls._providers[slug] = provider
        return provider

    @classmethod
    def get(cls, slug: str) -> IntegrationProvider | None:
        return cls._providers.get(slug)

    @classmethod
    def all(cls) -> list[IntegrationProvider]:
        return list(cls._providers.values())

    @classmethod
    def clear(cls) -> None:  # tests only
        cls._providers = {}
