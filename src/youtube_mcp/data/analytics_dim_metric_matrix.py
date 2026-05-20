"""Curated YouTube Analytics reports.query dimension/metric matrix."""

from __future__ import annotations

from typing import Final, TypedDict


class AnalyticsReportDefinition(TypedDict):
    """Supported dimensions and metrics for a report family."""

    report_type: str
    name: str
    ids_prefixes: tuple[str, ...]
    dimensions: tuple[str, ...]
    metrics: tuple[str, ...]


ANALYTICS_REPORT_SOURCES: Final[tuple[str, ...]] = (
    "https://developers.google.com/youtube/analytics/channel_reports",
    "https://developers.google.com/youtube/analytics/content_owner_reports",
    "https://developers.google.com/youtube/analytics/dimensions",
    "https://developers.google.com/youtube/analytics/metrics",
)

CORE_METRICS: Final[tuple[str, ...]] = (
    "views",
    "redViews",
    "estimatedMinutesWatched",
    "estimatedRedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "comments",
    "likes",
    "dislikes",
    "shares",
    "subscribersGained",
    "subscribersLost",
    "videosAddedToPlaylists",
    "videosRemovedFromPlaylists",
)

REVENUE_METRICS: Final[tuple[str, ...]] = (
    "estimatedRevenue",
    "estimatedAdRevenue",
    "grossRevenue",
    "estimatedRedPartnerRevenue",
    "monetizedPlaybacks",
    "playbackBasedCpm",
    "cpm",
    "adImpressions",
)

PLAYLIST_METRICS: Final[tuple[str, ...]] = (
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "playlistStarts",
    "viewsPerPlaylistStart",
    "averageTimeInPlaylist",
)

DEMOGRAPHIC_METRICS: Final[tuple[str, ...]] = ("viewerPercentage",)

RETENTION_METRICS: Final[tuple[str, ...]] = (
    "audienceWatchRatio",
    "relativeRetentionPerformance",
)

ANNOTATION_METRICS: Final[tuple[str, ...]] = (
    "annotationImpressions",
    "annotationClickableImpressions",
    "annotationClicks",
    "annotationClickThroughRate",
    "annotationClosableImpressions",
    "annotationCloses",
    "annotationCloseRate",
)

CARD_METRICS: Final[tuple[str, ...]] = (
    "cardImpressions",
    "cardClicks",
    "cardClickRate",
    "cardTeaserImpressions",
    "cardTeaserClicks",
    "cardTeaserClickRate",
)

END_SCREEN_METRICS: Final[tuple[str, ...]] = (
    "endScreenElementImpressions",
    "endScreenElementClicks",
    "endScreenElementClickRate",
)

CHANNEL_CORE_DIMENSIONS: Final[tuple[str, ...]] = (
    "day",
    "month",
    "country",
    "province",
    "video",
    "playlist",
    "group",
    "subscribedStatus",
    "youtubeProduct",
    "liveOrOnDemand",
    "creatorContentType",
    "sharingService",
    "insightPlaybackLocationType",
    "insightPlaybackLocationDetail",
    "insightTrafficSourceType",
    "insightTrafficSourceDetail",
    "deviceType",
    "operatingSystem",
)

CONTENT_OWNER_CORE_DIMENSIONS: Final[tuple[str, ...]] = (
    "day",
    "month",
    "channel",
    "video",
    "asset",
    "assetType",
    "claimedStatus",
    "uploaderType",
    "country",
    "province",
    "playlist",
    "group",
    "subscribedStatus",
    "youtubeProduct",
    "liveOrOnDemand",
    "creatorContentType",
    "insightPlaybackLocationType",
    "insightPlaybackLocationDetail",
    "insightTrafficSourceType",
    "insightTrafficSourceDetail",
    "deviceType",
    "operatingSystem",
)

ANALYTICS_DIM_METRIC_MATRIX: Final[tuple[AnalyticsReportDefinition, ...]] = (
    {
        "report_type": "channel",
        "name": "Channel core activity and engagement",
        "ids_prefixes": ("channel==",),
        "dimensions": CHANNEL_CORE_DIMENSIONS,
        "metrics": CORE_METRICS + REVENUE_METRICS,
    },
    {
        "report_type": "channel",
        "name": "Channel demographics",
        "ids_prefixes": ("channel==",),
        "dimensions": ("ageGroup", "gender", "video", "group"),
        "metrics": DEMOGRAPHIC_METRICS,
    },
    {
        "report_type": "channel",
        "name": "Channel playlist performance",
        "ids_prefixes": ("channel==",),
        "dimensions": ("playlist", "group", "day", "month", "country", "province", "video"),
        "metrics": PLAYLIST_METRICS,
    },
    {
        "report_type": "channel",
        "name": "Channel audience retention",
        "ids_prefixes": ("channel==",),
        "dimensions": ("elapsedVideoTimeRatio", "video", "group"),
        "metrics": RETENTION_METRICS,
    },
    {
        "report_type": "channel",
        "name": "Channel annotations, cards, and end screens",
        "ids_prefixes": ("channel==",),
        "dimensions": ("video", "group", "day", "month"),
        "metrics": ANNOTATION_METRICS + CARD_METRICS + END_SCREEN_METRICS,
    },
    {
        "report_type": "contentOwner",
        "name": "Content owner core activity and engagement",
        "ids_prefixes": ("contentOwner==",),
        "dimensions": CONTENT_OWNER_CORE_DIMENSIONS,
        "metrics": CORE_METRICS + REVENUE_METRICS,
    },
    {
        "report_type": "contentOwner",
        "name": "Content owner demographics",
        "ids_prefixes": ("contentOwner==",),
        "dimensions": ("ageGroup", "gender", "channel", "video", "group"),
        "metrics": DEMOGRAPHIC_METRICS,
    },
    {
        "report_type": "contentOwner",
        "name": "Content owner playlist performance",
        "ids_prefixes": ("contentOwner==",),
        "dimensions": (
            "playlist",
            "group",
            "channel",
            "video",
            "day",
            "month",
            "country",
            "province",
        ),
        "metrics": PLAYLIST_METRICS,
    },
    {
        "report_type": "contentOwner",
        "name": "Content owner audience retention",
        "ids_prefixes": ("contentOwner==",),
        "dimensions": ("elapsedVideoTimeRatio", "video", "group", "channel"),
        "metrics": RETENTION_METRICS,
    },
    {
        "report_type": "contentOwner",
        "name": "Content owner annotations, cards, and end screens",
        "ids_prefixes": ("contentOwner==",),
        "dimensions": ("video", "group", "channel", "day", "month"),
        "metrics": ANNOTATION_METRICS + CARD_METRICS + END_SCREEN_METRICS,
    },
)


def describe_analytics_matrix() -> dict[str, object]:
    """Return a JSON-serializable representation of the analytics matrix."""

    reports: list[dict[str, object]] = []
    for report in ANALYTICS_DIM_METRIC_MATRIX:
        reports.append(
            {
                "report_type": report["report_type"],
                "name": report["name"],
                "ids_prefixes": list(report["ids_prefixes"]),
                "dimensions": list(report["dimensions"]),
                "metrics": list(report["metrics"]),
            }
        )
    return {"sources": list(ANALYTICS_REPORT_SOURCES), "reports": reports}
