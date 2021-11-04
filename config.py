way_tags_to_keep = [
    # general informations,
    'name',
    'highway',
    'footway',
    'oneway',
    'surface',
    # lanes informations
    'lanes',
    'lanes:backward',
    'lanes:forward',
    # turn informations
    'turn:lanes',
    'turn:lanes:backward',
    'turn:lanes:forward',
    #cycling informations
    'bicycle',
    'segregated',
    'cycleway',
    'cycleway:right',
    'cycleway:left',
    'cycleway:both',
    # sidewalk informations
    'sidewalk',
    'sidewalk:left',
    'sidewalk:right',
    'sidewalk:both',
    # public transportation informations,
    'bus',
    'busway:right',
    'busway:left',
    'psv',
    'psv:lanes:backward',
    'psv:lanes:forward'
]

node_tags_to_keep = [
    # general informations
    'highway',
    # crosswalk informations
    'crossing',
    'tactile_paving',
    # traffic signals informations
    'traffic_signals',
    'traffic_signals:direction',
    'traffic_signals:sound',
    'button_operated'
    #sidewalk informations
    'kerb',
    #island informations
    'crossing:island'
]