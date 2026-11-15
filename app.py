"""
Ethnic Sets Deal Finder: a Streamlit dashboard over scraped Flipkart data.

Run locally:   streamlit run app.py
Refresh data:  python scraper.py   (then restart / refresh the app)
"""

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Ethnic Sets Deal Finder", layout="wide")

CHART_COLOR = "#2a78d6"   # one hue for every chart: each chart shows a single series

# Keywords are checked in order, so multi-word fabrics ("Cotton Blend")
# must come before the single word they contain ("Cotton").
FABRICS = [
    "Cotton Blend", "Pure Cotton", "Cotton Rayon", "Viscose Rayon", "Silk Blend",
    "Art Silk", "Tussar Silk", "Chanderi", "Georgette", "Velvet", "Crepe", "Chiffon",
    "Organza", "Muslin", "Linen", "Polyester", "Rayon", "Silk", "Cotton",
]
BOTTOMS = ["Palazzo", "Sharara", "Patiala", "Salwar", "Churidar", "Dhoti", "Skirt", "Pant", "Trouser"]


def find_keyword(title, keywords, default):
    title = str(title).lower()
    for word in keywords:
        if word.lower() in title:
            return word
    return default


@st.cache_data
def load_data(path="products.csv"):
    df = pd.read_csv(path)
    df["savings"] = df["mrp"] - df["price"]
    df["fabric"] = df["title"].apply(find_keyword, args=(FABRICS, "Not specified"))
    df["bottom"] = (
        df["title"].apply(find_keyword, args=(BOTTOMS, "Other"))
        .replace({"Pant": "Pant / Trouser", "Trouser": "Pant / Trouser"})
    )
    df["has_dupatta"] = df["title"].str.contains("dupatta", case=False)
    return df


def style_chart(fig, x_title, y_title):
    fig.update_traces(marker_color=CHART_COLOR)
    fig.update_layout(
        xaxis_title=x_title, yaxis_title=y_title,
        margin=dict(l=10, r=10, t=10, b=10), height=340, showlegend=False,
    )
    return fig


df = load_data()
has_ratings = df["rating"].notna().any()

# ---------------------------------------------------------------- header
st.title("Ethnic Sets Deal Finder")
st.markdown(
    "Women's ethnic sets on **Flipkart with 70%+ discount**, scraped with Python "
    "(`requests` + the page's embedded JSON) and explored with Streamlit."
)
st.caption(f"Data last scraped: {df['scraped_at'].iloc[0]}  ·  {len(df)} products  ·  {df['brand'].nunique()} brands")

# ---------------------------------------------------------------- sidebar filters
st.sidebar.header("Filters")
search = st.sidebar.text_input("Search brand or title", placeholder="e.g. Anarkali, Skylee")

min_p, max_p = int(df["price"].min()), int(df["price"].max())
price_range = st.sidebar.slider("Price (₹)", min_p, max_p, (min_p, max_p), step=10)

min_discount = st.sidebar.slider(
    "Minimum discount (%)", int(df["discount_pct"].min()), int(df["discount_pct"].max()),
    int(df["discount_pct"].min()),
)

fabric_options = df["fabric"].value_counts().index.tolist()
fabrics = st.sidebar.multiselect("Fabric", fabric_options, placeholder="All fabrics")

bottom_options = df["bottom"].value_counts().index.tolist()
bottoms = st.sidebar.multiselect("Bottom style", bottom_options, placeholder="All styles")

dupatta_only = st.sidebar.checkbox("Only sets with a dupatta")

min_rating = 0.0
if has_ratings:   # Flipkart doesn't always send ratings, so only show this when we have them
    min_rating = st.sidebar.slider("Minimum rating", 0.0, 5.0, 0.0, step=0.5)

sort_options = {
    "Biggest discount": ("discount_pct", False),
    "Lowest price": ("price", True),
    "Highest price": ("price", False),
    "Biggest ₹ saving": ("savings", False),
}
sort_by = st.sidebar.selectbox("Sort by", list(sort_options))

# ---------------------------------------------------------------- apply filters
view = df[df["price"].between(*price_range) & (df["discount_pct"] >= min_discount)]
if search:
    text = view["brand"] + " " + view["title"]
    view = view[text.str.contains(search, case=False, regex=False)]
if fabrics:
    view = view[view["fabric"].isin(fabrics)]
if bottoms:
    view = view[view["bottom"].isin(bottoms)]
if dupatta_only:
    view = view[view["has_dupatta"]]
if has_ratings and min_rating > 0:
    view = view[view["rating"] >= min_rating]

column, ascending = sort_options[sort_by]
view = view.sort_values(column, ascending=ascending)

if view.empty:
    st.warning("No products match these filters. Try widening the price range or clearing a filter.")
    st.stop()

# ---------------------------------------------------------------- KPI row
k1, k2, k3, k4 = st.columns(4)
k1.metric("Products", f"{len(view)}")
k2.metric("Median price", f"₹{view['price'].median():,.0f}")
k3.metric("Average discount", f"{view['discount_pct'].mean():.0f}%")
k4.metric("Biggest saving", f"₹{view['savings'].max():,.0f}")

browse_tab, insights_tab, data_tab = st.tabs(["Browse deals", "Insights", "Data"])

# ---------------------------------------------------------------- browse tab
with browse_tab:
    shown = view.head(40)
    if len(view) > 40:
        st.caption(f"Showing the top 40 of {len(view)} products. Use the filters to narrow down.")
    cols = st.columns(4)
    for i, row in enumerate(shown.itertuples()):
        with cols[i % 4].container(border=True):
            if isinstance(row.image_url, str):
                # fixed 5:6 frame so every card lines up, whatever the photo's size
                st.markdown(
                    f'<img src="{row.image_url}" alt="{row.title}" style="width:100%;'
                    f'aspect-ratio:5/6;object-fit:cover;border-radius:6px">',
                    unsafe_allow_html=True,
                )
            st.markdown(f"**{row.brand}**  \n{row.title}")
            st.markdown(f"### ₹{row.price:,.0f}")
            st.markdown(f"~~₹{row.mrp:,.0f}~~ · **{row.discount_pct}% off**  \nYou save ₹{row.savings:,.0f}")
            if has_ratings and pd.notna(row.rating):
                st.caption(f"Rating {row.rating} / 5 ({int(row.rating_count):,} ratings)")
            st.link_button("View on Flipkart", row.product_url, width="stretch")

# ---------------------------------------------------------------- insights tab
with insights_tab:
    left, right = st.columns(2)

    with left:
        st.subheader("How are prices spread?")
        fig = px.histogram(view, x="price", nbins=20)
        fig.update_traces(hovertemplate="₹%{x}<br>%{y} products<extra></extra>")
        fig.update_layout(bargap=0.08)
        st.plotly_chart(style_chart(fig, "Sale price (₹)", "Number of products"), width="stretch")

    with right:
        st.subheader("Brands with the most deals")
        top_brands = view["brand"].value_counts().head(10).sort_values()
        fig = px.bar(x=top_brands.values, y=top_brands.index, orientation="h")
        fig.update_traces(marker_cornerradius=4, hovertemplate="%{y}: %{x} products<extra></extra>")
        st.plotly_chart(style_chart(fig, "Number of products", None), width="stretch")

    left, right = st.columns(2)

    with left:
        st.subheader("Median price by fabric")
        by_fabric = (
            view.groupby("fabric")
            .agg(median_price=("price", "median"), products=("price", "size"))
            .query("products >= 3")          # 1–2 products is too few to compare fairly
            .sort_values("median_price")
            .reset_index()
        )
        st.caption("Fabrics with at least 3 products in the current selection.")
        fig = px.bar(by_fabric, x="median_price", y="fabric", orientation="h", custom_data=["products"])
        fig.update_traces(
            marker_cornerradius=4,
            hovertemplate="%{y}<br>Median ₹%{x:,.0f}<br>%{customdata[0]} products<extra></extra>",
        )
        st.plotly_chart(style_chart(fig, "Median sale price (₹)", None), width="stretch")

    with right:
        st.subheader("Original price (MRP) vs sale price")
        fig = px.scatter(view, x="mrp", y="price", custom_data=["brand", "discount_pct"])
        fig.update_traces(
            marker=dict(size=9, opacity=0.7, line=dict(width=1, color="rgba(255,255,255,0.8)")),
            hovertemplate="%{customdata[0]}<br>MRP ₹%{x:,}<br>Sale ₹%{y:,}<br>%{customdata[1]}% off<extra></extra>",
        )
        st.plotly_chart(style_chart(fig, "MRP (₹)", "Sale price (₹)"), width="stretch")

    insight = (
        f"Across {len(view)} product{'s' if len(view) != 1 else ''}, the average shopper saves "
        f"**₹{view['savings'].mean():,.0f}** off MRP."
    )
    if not by_fabric.empty:
        cheapest = by_fabric.iloc[0]
        insight += (
            f" The lowest median price is for **{cheapest['fabric']}** sets "
            f"(₹{cheapest['median_price']:,.0f} across {cheapest['products']} products)."
        )
    st.info(insight)

# ---------------------------------------------------------------- data tab
with data_tab:
    table_cols = ["image_url", "brand", "title", "fabric", "bottom", "price", "mrp", "discount_pct", "savings", "product_url"]
    if has_ratings:
        table_cols.insert(8, "rating")
    st.dataframe(
        view[table_cols],
        hide_index=True,
        width="stretch",
        column_config={
            "image_url": st.column_config.ImageColumn("Image"),
            "brand": "Brand",
            "title": "Title",
            "fabric": "Fabric",
            "bottom": "Bottom",
            "rating": "Rating",
            "price": st.column_config.NumberColumn("Price", format="₹%d"),
            "mrp": st.column_config.NumberColumn("MRP", format="₹%d"),
            "discount_pct": st.column_config.NumberColumn("Discount", format="%d%%"),
            "savings": st.column_config.NumberColumn("Saving", format="₹%d"),
            "product_url": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )
    st.download_button(
        "Download filtered data (CSV)",
        view.to_csv(index=False).encode("utf-8"),
        file_name="flipkart_ethnic_sets.csv",
        mime="text/csv",
    )

st.divider()
st.caption("Built with Python · requests · pandas · Plotly · Streamlit. Data is for learning purposes only.")
