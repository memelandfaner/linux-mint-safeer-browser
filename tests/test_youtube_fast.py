import unittest
from core.youtube_fast import extract_video_renderers, parse_video_renderer


class TestYouTubeFast(unittest.TestCase):
    def test_extract_video_renderers(self):
        sample = {
            "contents": {
                "twoColumnSearchResultsRenderer": {
                    "primaryContents": {
                        "sectionListRenderer": {
                            "contents": [
                                {
                                    "itemSectionRenderer": {
                                        "contents": [
                                            {
                                                "videoRenderer": {
                                                    "videoId": "abc123XYZ",
                                                    "title": {"runs": [{"text": "Test Video Title"}]},
                                                    "ownerText": {"runs": [{"text": "Test Channel"}]},
                                                    "lengthText": {"simpleText": "3:45"},
                                                    "viewCountText": {"simpleText": "1.2M views"},
                                                    "publishedTimeText": {"simpleText": "2 days ago"},
                                                    "thumbnail": {
                                                        "thumbnails": [
                                                            {"url": "https://i.ytimg.com/vi/abc123XYZ/hqdefault.jpg"}
                                                        ]
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        renderers = extract_video_renderers(sample)
        self.assertEqual(len(renderers), 1)
        item = parse_video_renderer(renderers[0])
        self.assertEqual(item["video_id"], "abc123XYZ")
        self.assertEqual(item["title"], "Test Video Title")
        self.assertEqual(item["channel"], "Test Channel")
        self.assertEqual(item["duration"], "3:45")
        self.assertEqual(item["views"], "1.2M views")
        self.assertEqual(item["published"], "2 days ago")
        self.assertEqual(item["thumbnail"], "https://i.ytimg.com/vi/abc123XYZ/hqdefault.jpg")
        self.assertEqual(item["url"], "https://www.youtube.com/watch?v=abc123XYZ")


if __name__ == "__main__":
    unittest.main()
