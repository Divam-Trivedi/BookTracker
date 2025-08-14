from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('',               views.home,             name='home'),
    path('library/',       views.my_library,       name='my_library'),
    path('surprise/',      views.surprise_start,   name='surprise_start'),
    path('surprise/result/', views.surprise_result, name='surprise_result'),
    path('add-to-library/<str:book_id>/', views.add_to_library, name='add_to_library'),
    path('update-status/<int:pk>/', views.update_status, name='update_status'),
    path('remove-book/<int:pk>/',     views.remove_book,     name='remove_book'),
    path('search/',        views.search_books,      name='search_books'),
    path('explore/',       views.explore_home,      name='explore_home'),
    path('explore/suggestions/', views.get_suggestions, name='get_suggestions'),
    path('explore/similar/', views.explore_similar, name='explore_similar'),
    path('explore/different/', views.explore_different, name='explore_different'),
    path('add-custom-book/', views.add_custom_book, name='add_custom_book'),
    path('login/', views.custom_login_view, name='login'),
    path('logout/', views.custom_logout_view, name='logout'),
    path('signup/', views.custom_signup_view, name='signup'),
]
