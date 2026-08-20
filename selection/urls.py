"""URL routes for the selection app."""
from django.urls import path

from .views import BoxListView, IndexView, ProductListView, RecommendView

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("api/recommend/", RecommendView.as_view(), name="recommend"),
    path("api/boxes/", BoxListView.as_view(), name="box-list"),
    path("api/products/", ProductListView.as_view(), name="product-list"),
]
