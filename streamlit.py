#!/usr/bin/env python
# coding: utf-8

# In[80]:


import pandas as pd
import streamlit as st
import folium
from streamlit_folium import folium_static
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd  # Assuming you're using pandas to manage your data
import openrouteservice
from openrouteservice import Client
from shapely.geometry import Point
import geopandas as gpd
from folium import GeoJson
import json
from folium.plugins import MarkerCluster
from shapely import wkt
import warnings
from openrouteservice import Client
warnings.filterwarnings('ignore')
import requests
from shapely.geometry import Polygon
import zipfile
import json


# In[81]:


st.set_page_config(layout='wide')
st.image('title.png', width=1200)
st.image('logo.png', width=1200)
st.sidebar.write('**demographic variable**')
demo_variable = st.sidebar.selectbox('Select preferred demographic variable', [
        'Population, Total', 'Population, Male', 'Population, Female', 
        'Population, Intersex', 'Sex Ratio (No. of Males per 100 Females)', 
        'Population Density (No. per Sq. Km)', 'Number of Households', 
        'Average Household size', 'Land Area (Sq. Km)', '% of population financially healthy'])
with st.sidebar.form("my_form"):
    # Input fields inside the form
    api_key = st.text_input("Enter your API Key")
    latitude = st.number_input('Enter latitude', value=0.0, format="%.6f")
    longitude = st.number_input('Enter longitude', value=0.0, format="%.6f")
    Branch = st.text_input('Enter branch name')
    isochrone_time = st.number_input('Enter isochrone time in minutes', min_value=1, value=15)
    color = st.selectbox('Select marker color', ['pink', 'blue', 'green', 'orange', 'red', 'darkblue', 'maroon'])
    
    # Submit button inside the form
    add_Location = st.form_submit_button('Add Location')


# In[107]:


@st.cache_data
def read_data():
    county_df = pd.read_csv('county_geometry_and_demographics.csv')
    county_df['geometry'] = county_df['geometry'].apply(wkt.loads)
    county_gdf = gpd.GeoDataFrame(county_df, geometry='geometry')

    if county_gdf.crs is None:
        county_gdf.set_crs(epsg=4326, inplace=True)
    elif county_gdf.crs.to_string() != 'EPSG:4326':
        county_gdf = county_gdf.to_crs(epsg=4326)

    return county_gdf


# In[117]:


if not api_key:
    default_key = 'e895c8773e1e452791addb66d57a41e9'
else:
    default_key = api_key

def create_choropleth():
    county_data = read_data()
    center_lat = 0.276134723744964
    center_lon = 43.5308662173491
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5.5)
    if not demo_variable or demo_variable not in county_data.columns:
        default_variable = 'Population Density (No. per Sq. Km)'
    else:
        default_variable = demo_variable
        folium.Choropleth(
            geo_data=county_data.to_json(),
            name='Choropleth',
            data=county_data,
            columns=['COUNTY', default_variable],
            key_on='feature.properties.COUNTY',
            fill_color='YlOrRd',
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name= default_variable
        ).add_to(fmap)
        # Optional: Add tooltips to show data on hover
        folium.GeoJson(
            county_data,
            tooltip=folium.GeoJsonTooltip(
            fields=['COUNTY', default_variable],
            style=("background-color: white; color: #333333; font-family: Arial; font-size: 12px; padding: 10px;")
            )
        ).add_to(fmap)
        return fmap


# In[125]:


@st.cache_data
def load_isochrones():
    zip_file_path = 'isochrones.zip'
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        with z.open('isochrones.json') as json_file:
            isochrones_list = json.load(json_file)

    iso_data_list = []  # Store processed GeoDataFrames and other data
    
    # Iterate over each isochrone in the list
    for isochrones in isochrones_list:
        if 'iso_data' in isochrones and 'features' in isochrones['iso_data']:
            # Extract the first feature from the GeoJSON data
            features = isochrones['iso_data']['features'][0]

            # Handle MultiPolygon geometry
            if features['geometry']['type'] == 'MultiPolygon':
                coordinates = features['geometry']['coordinates'][0][0]  # First polygon, first ring
                polygon_geom = Polygon(coordinates)

                # Create GeoDataFrame from the Polygon
                iso_gdf = gpd.GeoDataFrame({'geometry': [polygon_geom]}, crs='EPSG:4326')
                iso_gdf = iso_gdf.to_crs(epsg=3857)  # Convert to EPSG:3857 for area calculations
                iso_gdf['area_km2'] = iso_gdf['geometry'].area / 1e6  # Calculate area in km²
                area = iso_gdf['area_km2'].sum()

                # Collect relevant data for each isochrone
                iso_data_list.append({
                    'gdf': iso_gdf,
                    'branch': isochrones['branch'],
                    'latitude': isochrones['latitude'],
                    'longitude': isochrones['longitude'],
                    'supermarket_chain': isochrones['supermarket_chain'],
                    'color': isochrones['color'],
                    'area': area
                })
        else:
            print(f"Error: Isochrone features not found for {isochrones['branch']}.")

    return iso_data_list  # Return the processed data for further use


# In[119]:


def show_isochrones():
    # Initialize the map using create_choropleth() or folium.Map()
    fmap = create_choropleth()  # Assuming you have a create_choropleth() function

    # Load the isochrone data using load_isochrones()
    iso_data_list = load_isochrones()

    # Add a marker and isochrone for each location
    for iso_data in iso_data_list:
        branch = iso_data['branch']
        latitude = iso_data['latitude']
        longitude = iso_data['longitude']
        color = iso_data['color']
        area = iso_data['area']
        iso_gdf = iso_data['gdf']

        # Add a marker for the store location
        folium.Marker(
            location=[latitude, longitude],
            tooltip=branch,
            icon=folium.Icon(color=color, icon='info-sign')  # Use color for marker
        ).add_to(fmap)

        # Add the isochrone polygon to the map
        folium.GeoJson(
            iso_gdf.to_crs(epsg=4326),  # Convert back to EPSG:4326 for display
            name=f'{branch} Isochrones',
            tooltip=folium.Tooltip(f"{branch} Isochrone area: {area:.2f} km²"),
            style_function=lambda x: {'fillColor': 'red', 'color': 'black', 'weight': 1, 'opacity': 0.5}
        ).add_to(fmap)

    # Return the map with markers and isochrones
    return fmap


# In[120]:


def new_isochrone(gdf, range_minutes=15):
    try:
        fmap = show_isochrones()  # Load the existing map
        url = f"https://api.geoapify.com/v1/isoline"
        for _, location in gdf.iterrows():  # Iterate through the new locations
            params = {
                "lat": location['latitude'],
                "lon": location['longitude'],
                "type": "time",  # Use 'time' for time-based isochrones
                "mode": "drive",  # Default to driving mode
                "range": range_minutes * 60,  # Convert minutes to seconds
                "apiKey": default_key
            }
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise error if the request fails
            iso = response.json()

            if iso and 'features' in iso:  # Check if the response contains isochrone features
                # Create a GeoDataFrame from the GeoJSON isochrone features
                iso_gdf = gpd.GeoDataFrame.from_features(iso['features'], crs='EPSG:4326')
                iso_gdf = iso_gdf.to_crs(epsg=3857)
                # Calculate the area in km²
                iso_gdf['area_km2'] = iso_gdf['geometry'].area / 1e6
                area = iso_gdf['area_km2'].sum()

                # Add the location marker and isochrone to the map
                folium.Marker(
                    location=[location['latitude'], location['longitude']],
                    tooltip=location['Branch'],
                    icon=folium.Icon(color=location['color'], icon='info-sign')
                ).add_to(fmap)
                
                folium.GeoJson(
                    iso_gdf.to_crs(epsg=4326),  # Reproject for display
                    name='Isochrones',
                    tooltip=folium.Tooltip(f"{location['Branch']} Isochrone area, Isochrone size {area:.2f} km²"),
                    style_function=lambda x: {'fillColor': 'blue', 'color': 'black', 'weight': 1, 'opacity': 0.5}
                ).add_to(fmap)
        return fmap
    except requests.RequestException as e:
        st.error(f"Failed to fetch new isochrones: {e}")
        return None


# In[122]:


if 'new_location_gdf' not in st.session_state:
    st.session_state.new_location_gdf = None

# When a new location is added
if add_Location:
    new_location = {
        'latitude': [latitude],
        'longitude': [longitude],
        'Branch': [Branch],
        'Supermarket_chain': ['New Store'],
        'color': [color],
        'geometry': [Point(longitude, latitude)]
    }
    new_location_gdf = gpd.GeoDataFrame(new_location, geometry='geometry', crs='EPSG:4326')
    st.session_state.new_location_gdf = new_location_gdf  # Store the new location in session state
    fmap = new_isochrone(st.session_state.new_location_gdf, isochrone_time)
else:
    # Check if a new location has already been stored in the session state
    if st.session_state.new_location_gdf is not None:
        fmap = new_isochrone(st.session_state.new_location_gdf, isochrone_time)  # Render map with new location
    else:
        fmap = show_isochrones()  # Render default map without new location

# Display the map
st_folium(fmap, width=1200, height=600)


# In[ ]:




