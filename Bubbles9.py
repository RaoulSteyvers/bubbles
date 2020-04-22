import argparse
import os.path
import pandas as pd
import numpy as np
import geopandas as gpd
import json
import shapely
import datetime
from operator import methodcaller

from bokeh.plotting import figure
from bokeh.io import output_file, show, curdoc
from bokeh.palettes import viridis, brewer
from bokeh.models import GeoJSONDataSource, HoverTool, ColumnDataSource, LinearColorMapper, ColorBar, Slider
from bokeh.layouts import column, row, gridplot, widgetbox

print(pd.__version__)

def is_valid_file(parser, arg):
    if not os.path.isfile(arg):
        parser.error("The file %s does not exist!" % arg)
    else:
        return open(arg, encoding = 'UTF-8')

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--inputfile', dest = 'infile1',
                    required = True, metavar = 'INPUT_FILE1',
                    help = 'The input csv file containing the absolute rates.',
                    type = lambda x: is_valid_file(parser, x))
parser.add_argument('-im', '--inputmap', dest = 'inmap',
                    required = True, metavar = 'INPUT_MAP',
                    help = 'The input shapefile to plot')

title = "Daily growth count per country"
args = parser.parse_args()

source = pd.read_csv(args.infile1, parse_dates = [0])
source['date'] = pd.to_datetime(source['date'])
shapefile = gpd.read_file(args.inmap)

count = source
change = count.diff(axis = 0)

growth = source.transpose() #transpose to wide
growth.index.name = 'country'

changeRate = growth.diff(axis = 1) # calculating change rate for each day, based on previous day

columns = ['NAME', 'geometry'] # for dropping all unneeded columns
shapefile = shapefile[columns]

antarctica = shapefile[ shapefile['NAME'] == 'Antarctica'].index
shapefile.drop(antarctica, inplace = True) #dropping Antarctica

###############################################################################
# GRAPHS ######################################################################

palette6 = brewer['Dark2'][6]
palette5 = brewer['Dark2'][5]

OldMax = source.select_dtypes(include=[np.number]).max().max()
OldMin = source.select_dtypes(include=[np.number]).min().min()
NewMax = 100

scaleFactor = (OldMax - OldMin) / NewMax
scaleFactor = float(scaleFactor)

x = growth.columns.values.tolist()
TOOLS = ('pan', 'wheel_zoom', 'reset', 'hover')

headerUSA = 'United States of America'

rescaled = count
rescaled = rescaled.drop(columns=('date'))
rescaled = rescaled / scaleFactor

N = len(source) # Amount of days for input
numbers = pd.DataFrame({ 'day' : range(0, N + 1 ,1)})
count['day'] = numbers['day']
rescaled['day'] = numbers['day']

big = count.merge(rescaled, how = 'left', left_on = 'day', right_on = 'day')

big = big.rename(columns={'United States of America_x': 'USA_x', 'United States of America_y': 'USA_y'})

countries_x = big.columns.values.tolist()
countries_y = countries_x[7:14]
del countries_x[7:14]

del countries_x[0]
del countries_y[0]

example_x = countries_x.pop(-1)
example_y = countries_y.pop(-1)

country_titles = ['China', 'Italy', 'Spain', 'Germany', 'Netherlands']

bigCDS = ColumnDataSource(data = big)

hover1 = HoverTool(names=[example_x, 'China_x', 'Italy_x', 'Spain_x', 'Germany_x', 'Netherlands_x'],
                  tooltips = [('Day', '@day'), ('Death count', '@$name')]
                  )

# example graph needed for linking x and y ranges

fHeight = 130
fWidth = 700

exampleGraph = figure(title = headerUSA,
                      plot_width = fWidth,
                      plot_height = fHeight,
                      y_range = (-500, 500),
                      tools = [hover1, 'pan', 'wheel_zoom', 'reset'],
                      )

exampleGraph.circle(x = 'day',
              y = 0,
              size = example_y,
              color = palette6[5],
              alpha = 0.2,
              name = example_x,
              source = bigCDS
)
exampleGraph.line(x = x,
            y = change[headerUSA],
            line_color = palette6[5],
            line_width = 1.5,
            line_alpha = 1,
)

plots = []
for country_title, country_x, country_y, i in zip(country_titles, countries_x, countries_y, range(5)):
    p = figure(title = country_title,
               plot_width = fWidth,
               plot_height = fHeight,
               x_range = exampleGraph.x_range,
               y_range = exampleGraph.y_range,
               tools = [hover1, 'pan', 'wheel_zoom', 'reset'],
               )
    glyphs = [[p.circle(x = 'day',
                 y = 0,
                 size = country_y,
                 color = palette5[i],
                 alpha = 0.2,
                 name = country_x,
                 source = bigCDS
                 )],
              [p.line(x = x,
                     y = change[country_titles[i]],
                     line_color = palette5[i],
                     line_width = 1.5,
                     line_alpha = 1)]
             ]
    plots.append(p)

#################################################################
# Cumulative graph

country_titles2 = ['China', 'Italy', 'Spain', 'Germany', 'Netherlands', 'United States of America']

countCopy = source

countCopy = countCopy.drop(columns=('date'))
dfSum = countCopy.cumsum(axis=0)
dfSum['day'] = numbers['day']

dfSumCDS = ColumnDataSource(data = dfSum)

hover2 = HoverTool(tooltips = [('Country', '$name'),
                               ('Cumulative count', '@$name')])


cumTotal = figure(title = 'Total count per country',
                  plot_width = 650,
                  plot_height = 400,
                  y_axis_type = "log",
                  tools = [hover2])

for country, i in zip(country_titles2, range (6)):
    cumTotal.line(x = 'day',
                  y = country,
                  line_color = palette6[i],
                  line_width = 2.5,
                  name = country,
                  source = dfSumCDS)

cumTotal.xaxis.axis_label = 'Day'

###############################################################################
# MAPS ######################################################################

hover3 = HoverTool(names = country_titles2,
                   tooltips = [('Country', '@NAME'),
                               ('Death count', '@rates')]
                  )

map = figure(title = 'Worldwide death count per day',
           plot_height = 300,
           plot_width = 650,
           toolbar_location = None,
           tools = [hover3, 'pan', 'wheel_zoom', 'reset']
)
map.xgrid.grid_line_color = None
map.ygrid.grid_line_color = None
map.axis.visible = False

basemap = shapefile.copy()

pointsfile = shapefile.copy()
pointsfile['centroid'] = pointsfile['geometry'].centroid
pointsfile["x"] = pointsfile.centroid.x
pointsfile["y"] = pointsfile.centroid.y
pointsfile = pointsfile.drop(columns=('centroid'))

pointsmerged = pointsfile.merge(growth, how = 'inner', left_on = 'NAME', right_on = 'country')

####################################################################

basemap_json = json.loads(basemap.to_json())
basemap_dump = json.dumps(basemap_json)
geobase = GeoJSONDataSource(geojson = basemap_dump)

map.patches(xs ='xs',
            ys = 'ys',
            source = geobase,
            fill_color = 'lightgray',
            line_color = 'white',
            line_width = 0.3,
            name = 'NAME')

scaleFactorMap = scaleFactor / 2

def get_data(selectedDay):
    day = selectedDay
    df_day = growth[day]
    pointsmerged = pointsfile.merge(df_day, left_on = 'NAME', right_on = 'country', how = 'left')
    pointsmerged['rates'] = pointsmerged[day]
    pointsmerged['scaledsize'] = pointsmerged['rates'] / scaleFactorMap
    points_json = json.loads(pointsmerged.to_json())
    get_data = json.dumps(points_json)
    return get_data

geopoints = GeoJSONDataSource(geojson = get_data(0))

datelist = pd.date_range(start = "2020-01-01", end = "2020-04-16")
datelist = datelist.map(methodcaller('strftime', '%d-%m-%Y'))

def update_plot(attr, old, new):
    day = slider.value
    date = datelist[day]
    new_data = get_data(day)
    geopoints.geojson = new_data
    map.title.text = 'Death count on date: %s' % date

slider = Slider(title = 'Selected day',
                start = min(x),
                end = max(x),
                step = 1,
                value = min(x),
                width = 650
)
slider.on_change('value', update_plot)

for country, i in zip(country_titles2, range (6)):
    map.circle(x = 'x',
               y = 'y',
               size = {'field' : 'scaledsize'},
               source = geopoints,
               alpha = 0.5,
               name = country,
               color = palette6[i],
               line_color = 'black',
               line_width = 0.1
               )

###############################################################################
# LAYOUT ######################################################################

left = column(exampleGraph, *plots)
right = column(map, widgetbox(slider), cumTotal)

both = gridplot([left, right], toolbar_location = 'left', ncols = 2)

curdoc().add_root(both)

output_file("graph01.html")
show(both)
