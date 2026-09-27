import os
from typing import Any

import pandas as pd
import plotly.express as px
import pycountry
import streamlit as st
from dotenv import load_dotenv

from dashboard.api_client import APIClient, APIClientError
from dashboard.data import (
	analyzed_count,
	article_table_rows,
	choices,
	country_counts,
	filter_articles,
	language_counts,
	sentiment_counts,
)


load_dotenv()
st.set_page_config(page_title="NewsPulse | Sentiment Analytics", page_icon="N", layout="wide")


def api_client() -> APIClient:
	return APIClient(base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))


def show_operation_result(title: str, result: dict[str, int]) -> None:
	st.success(title)
	columns = st.columns(len(result))
	for column, (label, value) in zip(columns, result.items()):
		column.metric(label.replace("_", " ").title(), value)


def render_sentiment_chart(articles: list[dict[str, Any]]) -> None:
	counts = sentiment_counts(articles)
	frame = pd.DataFrame({"Sentiment": [key.title() for key in counts], "Articles": list(counts.values())})
	figure = px.bar(
		frame,
		x="Sentiment",
		y="Articles",
		color="Sentiment",
		color_discrete_map={"Positive": "#17805c", "Neutral": "#7b8794", "Negative": "#c94c4c"},
		text_auto=True,
	)
	figure.update_layout(showlegend=False, margin={"t": 20, "r": 10, "b": 10, "l": 10})
	st.plotly_chart(figure, width="stretch", theme=None)


def render_language_chart(articles: list[dict[str, Any]]) -> None:
	counts = language_counts(articles)
	if not counts:
		st.info("No language metadata is available for the current selection.")
		return
	frame = pd.DataFrame({"Language": list(counts), "Articles": list(counts.values())})
	figure = px.bar(frame, x="Articles", y="Language", orientation="h", text_auto=True)
	figure.update_layout(margin={"t": 20, "r": 10, "b": 10, "l": 10}, yaxis={"categoryorder": "total ascending"})
	st.plotly_chart(figure, width="stretch", theme=None)


def country_map_frame(articles: list[dict[str, Any]]) -> tuple[pd.DataFrame, int]:
	counts = country_counts(articles)
	rows: list[dict[str, Any]] = []
	for country, article_count in counts.items():
		record = pycountry.countries.get(alpha_2=country)
		if record is not None:
			rows.append({"country": record.alpha_3, "country_name": record.name, "Articles": article_count})
	missing_count = sum(1 for article in articles if not article.get("country"))
	return pd.DataFrame(rows), missing_count


def render_country_map(articles: list[dict[str, Any]]) -> None:
	frame, missing_count = country_map_frame(articles)
	if frame.empty:
		st.info("No valid country metadata is available for the current selection.")
	else:
		figure = px.choropleth(
			frame,
			locations="country",
			color="Articles",
			hover_name="country_name",
			locationmode="ISO-3",
			color_continuous_scale="Tealgrn",
		)
		figure.update_layout(margin={"t": 0, "r": 0, "b": 0, "l": 0})
		st.plotly_chart(figure, width="stretch", theme=None)
	if missing_count:
		st.caption(f"{missing_count} article(s) have no country metadata and are excluded from the map.")


def render_article_details(client: APIClient, articles: list[dict[str, Any]]) -> None:
	if not articles:
		return
	options = {
		f"{article.get('title', 'Untitled')} [{article.get('id', 'unknown')}]": article.get("id")
		for article in articles
	}
	selected_label = st.selectbox("Inspect an article", ["None", *options.keys()])
	if selected_label == "None":
		return
	try:
		article = client.get_article(options[selected_label])
	except APIClientError as error:
		st.error(str(error))
		return
	st.subheader(article.get("title") or "Untitled")
	st.write(article.get("description") or "No description available.")
	details = st.columns(4)
	for column, label, value in (
		(details[0], "Source", article.get("source") or "Unknown"),
		(details[1], "Author", article.get("author") or "Unknown"),
		(details[2], "Country", article.get("country") or "Unknown"),
		(details[3], "Language", article.get("language_detected") or article.get("language") or "Unknown"),
	):
		column.caption(label)
		column.write(value)
	st.write(f"Sentiment: {article.get('sentiment_label') or 'Not analyzed'}")
	confidence = article.get("sentiment_confidence")
	st.write(f"Confidence: {confidence:.1%}" if isinstance(confidence, (int, float)) else "Confidence: -")
	st.write(f"Analysis text: {article.get('analysis_text') or 'Not analyzed'}")
	if article.get("url"):
		st.link_button("Open original article", article["url"])


def main() -> None:
	client = api_client()
	st.markdown("# NewsPulse")
	st.caption("Multilingual News Sentiment Analytics")

	try:
		health = client.health()
		st.sidebar.success(f"API online: {health.get('status', 'unknown')}")
	except APIClientError as error:
		st.sidebar.error(str(error))
		st.warning("Start FastAPI with `uvicorn backend.app.main:app --reload` to load live articles.")
		return

	with st.sidebar:
		st.header("Controls")
		if st.button("Refresh data", width="stretch"):
			st.rerun()
		limit = st.slider("Article limit", min_value=10, max_value=200, value=100, step=10)
		if st.button("Fetch Latest News", width="stretch"):
			try:
				show_operation_result("Latest news fetched.", client.fetch_articles(limit=min(limit, 20)))
			except APIClientError as error:
				st.error(str(error))
		if st.button("Analyze Unprocessed Articles", width="stretch"):
			try:
				show_operation_result("Article analysis completed.", client.analyze_articles(limit=limit))
			except APIClientError as error:
				st.error(str(error))

	try:
		articles = client.list_articles(limit=200)
	except APIClientError as error:
		st.error(str(error))
		return
	if not articles:
		st.info("No articles are available yet. Use Fetch Latest News to populate the dashboard.")
		return

	sentiment = st.sidebar.selectbox("Sentiment", ["All", *choices(articles, "sentiment_label")], key="sentiment_filter")
	language = st.sidebar.selectbox("Language", ["All", *choices(articles, "language")], key="language_filter")
	country = st.sidebar.selectbox("Country", ["All", *choices(articles, "country")], key="country_filter")
	category = st.sidebar.selectbox("Category", ["All", *choices(articles, "category")], key="category_filter")
	if st.sidebar.button("Clear filters", width="stretch"):
		for key in ("sentiment_filter", "language_filter", "country_filter", "category_filter"):
			st.session_state.pop(key, None)
		st.rerun()

	selected = filter_articles(articles, sentiment=sentiment, language=language, country=country, category=category)
	counts = sentiment_counts(selected)
	metrics = st.columns(5)
	metrics[0].metric("Total Articles", len(selected))
	metrics[1].metric("Positive", counts["positive"])
	metrics[2].metric("Neutral", counts["neutral"])
	metrics[3].metric("Negative", counts["negative"])
	metrics[4].metric("Analyzed", analyzed_count(selected))

	st.divider()
	left, right = st.columns(2)
	with left:
		st.subheader("Sentiment distribution")
		render_sentiment_chart(selected)
	with right:
		st.subheader("Language distribution")
		render_language_chart(selected)
	st.subheader("Geographic distribution")
	render_country_map(selected)

	st.subheader("Recent articles")
	rows = article_table_rows(selected)
	if rows:
		st.dataframe(
			pd.DataFrame(rows),
			column_config={
				"URL": st.column_config.LinkColumn("URL"),
				"Confidence": st.column_config.NumberColumn("Confidence", format="%.1%%"),
			},
			hide_index=True,
			width="stretch",
		)
	else:
		st.info("No articles match the selected filters.")
	st.divider()
	st.subheader("Article details")
	render_article_details(client, selected)


if __name__ == "__main__":
	main()