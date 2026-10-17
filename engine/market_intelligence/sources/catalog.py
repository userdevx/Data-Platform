from __future__ import annotations

from engine.market_intelligence.sources.models import (
    InformationSource,
)
from engine.market_intelligence.sources.registry import (
    InformationSourceRegistry,
)


def _information_source(
    *,
    source_id: str,
    name: str,
    source_type: str,
    authority: str,
    domains: tuple[str, ...],
    source_url: str,
    documentation_url: str,
    api_available: bool | None,
    stream_available: bool | None,
    bulk_download_available: bool | None,
    authentication_required: bool | None,
    collector_implemented: bool = False,
    ingestion_enabled: bool = False,
    api_url: str | None = None,
    stream_url: str | None = None,
    bulk_url: str | None = None,
    license_name: str | None = None,
) -> InformationSource:
    """
    Construct a registered information source.

    Registration means the Data Platform recognizes
    the provider.

    It does not mean a collector exists or that
    ingestion is enabled.

    Restricted-use policy fields intentionally remain
    None until independently reviewed.
    """

    return InformationSource(
        source_id=source_id,
        name=name,
        source_type=source_type,
        authority=authority,
        domains=domains,

        registered=True,
        enabled=True,

        collector_implemented=(
            collector_implemented
        ),
        ingestion_enabled=(
            ingestion_enabled
        ),

        cost_free=None,
        authentication_required=(
            authentication_required
        ),

        api_available=api_available,
        stream_available=stream_available,
        bulk_download_available=(
            bulk_download_available
        ),

        raw_storage_allowed=None,
        commercial_use_allowed=None,
        raw_redistribution_allowed=None,
        derived_analysis_allowed=None,
        model_training_allowed=None,

        attribution_required=None,
        share_alike_required=None,

        license_name=license_name,

        source_url=source_url,
        documentation_url=(
            documentation_url
        ),

        api_url=api_url,
        stream_url=stream_url,
        bulk_url=bulk_url,
    )


INFORMATION_SOURCES = (
    _information_source(
        source_id="wikidata",
        name="Wikidata",
        source_type="structured_knowledge",
        authority=(
            "collaborative_structured_reference"
        ),
        domains=(
            "entities",
            "organizations",
            "people",
            "products",
            "places",
            "works",
            "relationships",
            "identifiers",
            "classifications",
        ),
        source_url=(
            "https://www.wikidata.org/"
        ),
        documentation_url=(
            "https://www.wikidata.org/wiki/"
            "Wikidata:Data_access"
        ),
        api_available=True,
        stream_available=True,
        bulk_download_available=True,
        authentication_required=False,
        api_url=(
            "https://www.wikidata.org/w/api.php"
        ),
        stream_url=(
            "https://stream.wikimedia.org/"
            "v2/stream/recentchange"
        ),
        bulk_url=(
            "https://dumps.wikimedia.org/"
            "wikidatawiki/"
        ),
        license_name="CC0 1.0",
    ),

    _information_source(
        source_id="sec_edgar",
        name="SEC EDGAR",
        source_type="regulatory_financial",
        authority=(
            "official_us_securities_regulator"
        ),
        domains=(
            "companies",
            "filings",
            "financial_facts",
            "regulatory_disclosures",
        ),
        source_url=(
            "https://www.sec.gov/edgar"
        ),
        documentation_url=(
            "https://www.sec.gov/search-filings/"
            "edgar-application-programming-interfaces"
        ),
        api_available=True,
        stream_available=None,
        bulk_download_available=True,
        authentication_required=False,
        api_url=(
            "https://data.sec.gov/"
        ),
    ),

    _information_source(
        source_id="gdelt",
        name="GDELT",
        source_type="global_events_news",
        authority=(
            "global_event_and_media_dataset"
        ),
        domains=(
            "events",
            "news_activity",
            "organizations",
            "locations",
            "topics",
            "media_velocity",
        ),
        source_url=(
            "https://www.gdeltproject.org/"
        ),
        documentation_url=(
            "https://www.gdeltproject.org/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=False,
        bulk_url=(
            "https://data.gdeltproject.org/"
        ),
    ),

    _information_source(
        source_id="bls",
        name=(
            "U.S. Bureau of Labor Statistics"
        ),
        source_type="official_economic",
        authority=(
            "official_us_labor_statistics"
        ),
        domains=(
            "employment",
            "unemployment",
            "wages",
            "prices",
            "productivity",
        ),
        source_url=(
            "https://www.bls.gov/"
        ),
        documentation_url=(
            "https://www.bls.gov/developers/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=False,
    ),

    _information_source(
        source_id="census",
        name="U.S. Census Bureau",
        source_type="official_statistics",
        authority=(
            "official_us_census_statistics"
        ),
        domains=(
            "population",
            "demographics",
            "housing",
            "income",
            "business",
            "geography",
        ),
        source_url=(
            "https://www.census.gov/"
        ),
        documentation_url=(
            "https://www.census.gov/"
            "data/developers.html"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=True,
        collector_implemented=True,
        ingestion_enabled=True,
        api_url=(
            "https://api.census.gov/data"
        ),
    ),

    _information_source(
        source_id="bea",
        name=(
            "Bureau of Economic Analysis"
        ),
        source_type="official_economic",
        authority=(
            "official_us_economic_statistics"
        ),
        domains=(
            "gdp",
            "industry",
            "income",
            "employment",
            "consumer_spending",
            "international_accounts",
        ),
        source_url=(
            "https://www.bea.gov/"
        ),
        documentation_url=(
            "https://apps.bea.gov/api/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=None,
        authentication_required=True,
        api_url=(
            "https://apps.bea.gov/api/"
        ),
    ),

    _information_source(
        source_id="treasury_fiscal_data",
        name="U.S. Treasury Fiscal Data",
        source_type="official_government_finance",
        authority=(
            "official_us_treasury"
        ),
        domains=(
            "federal_debt",
            "revenue",
            "spending",
            "cash_balances",
            "fiscal_operations",
        ),
        source_url=(
            "https://fiscaldata.treasury.gov/"
        ),
        documentation_url=(
            "https://fiscaldata.treasury.gov/"
            "api-documentation/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=None,
        authentication_required=False,
    ),

    _information_source(
        source_id="fred",
        name=(
            "Federal Reserve Economic Data"
        ),
        source_type="economic_time_series",
        authority=(
            "economic_data_aggregation_service"
        ),
        domains=(
            "interest_rates",
            "inflation",
            "employment",
            "financial_conditions",
            "economic_indicators",
        ),
        source_url=(
            "https://fred.stlouisfed.org/"
        ),
        documentation_url=(
            "https://fred.stlouisfed.org/"
            "docs/api/fred/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=None,
        authentication_required=True,
    ),

    _information_source(
        source_id="world_bank",
        name="World Bank",
        source_type="global_economic",
        authority=(
            "international_development_institution"
        ),
        domains=(
            "population",
            "gdp",
            "trade",
            "development",
            "education",
            "energy",
            "poverty",
            "health",
            "debt",
        ),
        source_url=(
            "https://www.worldbank.org/"
        ),
        documentation_url=(
            "https://datahelpdesk.worldbank.org/"
            "knowledgebase/articles/889392"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=None,
        authentication_required=False,
    ),

    _information_source(
        source_id="crossref",
        name="Crossref",
        source_type="scholarly_metadata",
        authority=(
            "scholarly_metadata_registry"
        ),
        domains=(
            "doi",
            "works",
            "authors",
            "publishers",
            "funders",
            "licenses",
            "references",
        ),
        source_url=(
            "https://www.crossref.org/"
        ),
        documentation_url=(
            "https://www.crossref.org/"
            "documentation/retrieve-metadata/rest-api/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=False,
        api_url=(
            "https://api.crossref.org/"
        ),
    ),

    _information_source(
        source_id="openalex",
        name="OpenAlex",
        source_type="research_graph",
        authority=(
            "open_research_graph"
        ),
        domains=(
            "works",
            "authors",
            "institutions",
            "topics",
            "publishers",
            "funders",
        ),
        source_url=(
            "https://openalex.org/"
        ),
        documentation_url=(
            "https://help.openalex.org/api/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=False,
    ),

    _information_source(
        source_id="arxiv",
        name="arXiv",
        source_type="research_metadata",
        authority=(
            "research_preprint_repository"
        ),
        domains=(
            "papers",
            "authors",
            "categories",
            "submission_dates",
            "research_metadata",
        ),
        source_url=(
            "https://arxiv.org/"
        ),
        documentation_url=(
            "https://info.arxiv.org/help/api/"
        ),
        api_available=True,
        stream_available=True,
        bulk_download_available=None,
        authentication_required=False,
    ),

    _information_source(
        source_id="ncbi_pubmed",
        name="PubMed / NCBI",
        source_type="biomedical_metadata",
        authority=(
            "us_biomedical_information_service"
        ),
        domains=(
            "biomedical_research",
            "citations",
            "publications",
            "mesh",
            "identifiers",
        ),
        source_url=(
            "https://pubmed.ncbi.nlm.nih.gov/"
        ),
        documentation_url=(
            "https://www.ncbi.nlm.nih.gov/"
            "books/NBK25501/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=False,
        api_url=(
            "https://eutils.ncbi.nlm.nih.gov/"
            "entrez/eutils/"
        ),
    ),

    _information_source(
        source_id="opencitations",
        name="OpenCitations",
        source_type="citation_graph",
        authority=(
            "open_citation_infrastructure"
        ),
        domains=(
            "citations",
            "references",
            "citation_counts",
            "research_relationships",
        ),
        source_url=(
            "https://opencitations.net/"
        ),
        documentation_url=(
            "https://api.opencitations.net/index/v2"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=None,
    ),

    _information_source(
        source_id="github",
        name="GitHub",
        source_type="software_activity",
        authority=(
            "software_collaboration_platform"
        ),
        domains=(
            "repositories",
            "releases",
            "issues",
            "pull_requests",
            "languages",
            "contributors",
            "software_activity",
        ),
        source_url=(
            "https://github.com/"
        ),
        documentation_url=(
            "https://docs.github.com/en/rest"
        ),
        api_available=True,
        stream_available=None,
        bulk_download_available=None,
        authentication_required=False,
        api_url=(
            "https://api.github.com/"
        ),
    ),

    _information_source(
        source_id="hacker_news",
        name="Hacker News",
        source_type="technology_discussion",
        authority=(
            "public_technology_discussion_signal"
        ),
        domains=(
            "technology",
            "stories",
            "comments",
            "jobs",
            "discussion_activity",
        ),
        source_url=(
            "https://news.ycombinator.com/"
        ),
        documentation_url=(
            "https://github.com/HackerNews/API"
        ),
        api_available=True,
        stream_available=True,
        bulk_download_available=False,
        authentication_required=False,
    ),

    _information_source(
        source_id="stack_exchange",
        name="Stack Exchange",
        source_type="developer_knowledge",
        authority=(
            "public_question_answer_network"
        ),
        domains=(
            "questions",
            "answers",
            "comments",
            "tags",
            "developer_activity",
        ),
        source_url=(
            "https://stackexchange.com/"
        ),
        documentation_url=(
            "https://api.stackexchange.com/docs"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=None,
        authentication_required=False,
    ),

    _information_source(
        source_id="openstreetmap",
        name="OpenStreetMap",
        source_type="geographic_data",
        authority=(
            "collaborative_geographic_database"
        ),
        domains=(
            "roads",
            "places",
            "points_of_interest",
            "transportation",
            "trails",
            "geographic_features",
        ),
        source_url=(
            "https://www.openstreetmap.org/"
        ),
        documentation_url=(
            "https://www.openstreetmap.org/copyright"
        ),
        api_available=True,
        stream_available=None,
        bulk_download_available=True,
        authentication_required=False,
        bulk_url=(
            "https://planet.openstreetmap.org/"
        ),
        license_name="ODbL",
    ),

    _information_source(
        source_id="nws",
        name="National Weather Service",
        source_type="weather",
        authority=(
            "official_us_weather_service"
        ),
        domains=(
            "forecasts",
            "alerts",
            "observations",
            "weather",
        ),
        source_url=(
            "https://www.weather.gov/"
        ),
        documentation_url=(
            "https://www.weather.gov/"
            "documentation/services-web-api"
        ),
        api_available=True,
        stream_available=None,
        bulk_download_available=None,
        authentication_required=False,
        api_url=(
            "https://api.weather.gov/"
        ),
    ),

    _information_source(
        source_id="noaa",
        name="NOAA / NCEI",
        source_type="environmental_climate",
        authority=(
            "official_us_environmental_data"
        ),
        domains=(
            "climate",
            "weather_history",
            "marine",
            "environment",
            "stations",
        ),
        source_url=(
            "https://www.noaa.gov/"
        ),
        documentation_url=(
            "https://www.ncei.noaa.gov/"
            "support/access-data-service-api-"
            "user-documentation"
        ),
        api_available=True,
        stream_available=None,
        bulk_download_available=True,
        authentication_required=None,
    ),

    _information_source(
        source_id="usgs",
        name="U.S. Geological Survey",
        source_type="earth_science",
        authority=(
            "official_us_earth_science_agency"
        ),
        domains=(
            "earthquakes",
            "geology",
            "water",
            "geography",
            "environment",
        ),
        source_url=(
            "https://www.usgs.gov/"
        ),
        documentation_url=(
            "https://earthquake.usgs.gov/"
            "fdsnws/event/1/"
        ),
        api_available=True,
        stream_available=True,
        bulk_download_available=None,
        authentication_required=False,
    ),

    _information_source(
        source_id="national_park_service",
        name="National Park Service",
        source_type="parks_travel",
        authority=(
            "official_us_national_parks_service"
        ),
        domains=(
            "parks",
            "visitor_centers",
            "campgrounds",
            "activities",
            "events",
            "alerts",
            "travel",
        ),
        source_url=(
            "https://www.nps.gov/"
        ),
        documentation_url=(
            "https://www.nps.gov/"
            "subjects/developer/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=None,
        authentication_required=True,
    ),

    _information_source(
        source_id="musicbrainz",
        name="MusicBrainz",
        source_type="music_metadata",
        authority=(
            "community_music_metadata_database"
        ),
        domains=(
            "artists",
            "releases",
            "recordings",
            "works",
            "labels",
            "music_relationships",
        ),
        source_url=(
            "https://musicbrainz.org/"
        ),
        documentation_url=(
            "https://musicbrainz.org/doc/"
            "MusicBrainz_API"
        ),
        api_available=True,
        stream_available=True,
        bulk_download_available=True,
        authentication_required=False,
        license_name=(
            "dataset-specific"
        ),
    ),

    _information_source(
        source_id="uspto_patentsview",
        name="USPTO / PatentsView",
        source_type="patent_innovation",
        authority=(
            "us_patent_information_service"
        ),
        domains=(
            "patents",
            "inventors",
            "assignees",
            "organizations",
            "technology",
            "innovation",
        ),
        source_url=(
            "https://patentsview.org/"
        ),
        documentation_url=(
            "https://search.patentsview.org/docs/"
        ),
        api_available=True,
        stream_available=False,
        bulk_download_available=True,
        authentication_required=True,
    ),
)


EXPECTED_INFORMATION_SOURCE_IDS = frozenset(
    {
        "wikidata",
        "sec_edgar",
        "gdelt",
        "bls",
        "census",
        "bea",
        "treasury_fiscal_data",
        "fred",
        "world_bank",
        "crossref",
        "openalex",
        "arxiv",
        "ncbi_pubmed",
        "opencitations",
        "github",
        "hacker_news",
        "stack_exchange",
        "openstreetmap",
        "nws",
        "noaa",
        "usgs",
        "national_park_service",
        "musicbrainz",
        "uspto_patentsview",
    }
)


def build_information_source_registry(
) -> InformationSourceRegistry:
    return InformationSourceRegistry(
        INFORMATION_SOURCES
    )
