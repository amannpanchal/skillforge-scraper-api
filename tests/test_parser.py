from app.main import _extract_page


def test_extracts_title_description_headings_and_text():
    html = """
    <html><head>
      <title>Demo Page</title>
      <meta name="description" content="A sample description">
      <link rel="canonical" href="https://example.com/canonical">
      <script>doNotInclude()</script>
    </head><body>
      <h1>Hello</h1><h2>World</h2><p>Readable text</p>
    </body></html>
    """
    result = _extract_page(html, "https://example.com", 200)
    assert result.title == "Demo Page"
    assert result.description == "A sample description"
    assert result.canonical_url == "https://example.com/canonical"
    assert result.headings == ["Hello", "World"]
    assert "Readable text" in result.text
    assert "doNotInclude" not in result.text
