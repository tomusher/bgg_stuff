import datetime, shelve, itertools, collections, shutil, os, time, math, operator

from PIL import Image
from jinja2 import Environment, FileSystemLoader
import requests

from boardgamegeek import BoardGameGeek

# IDs of active Snowdonia Dragons attendees.
# Doing it this way rather than fetching the whole guild because we have
# a few members that don't actively attend sessions.
SD_USERS = ['avlawn', 'boyuki', 'dheath3266', 'Draddict', 'Endenisia', 'FungalBoar9',
            'Gaelgog', 'Manicat', 'MrJuggles', 'NotBrian', 'pebold', 'ResidentGnome',
            'silverrobert', 'Straight%20To%20Hell', 'tomusher', 'twrchtrwyth']
START_DATE = datetime.date(2014, 1, 1)
END_DATE = datetime.date(2014, 12, 31)
IMAGE_WIDTH = 100
MAX_IMAGE_WIDTH = 500

def prepare_build():
    shutil.rmtree('build')
    os.mkdir('build')
    os.mkdir('build/images')
    shutil.copytree('static', 'build/static')

def get_plays_for_users(users, start_date, end_date):
    """ Given a list of users, return a dictionary of play sessions for each. """
    plays = {}
    for user in users:
        print("Getting plays for user: {0}".format(user))
        try:
            plays[user] = store[user]
        except KeyError:
            plays[user] = []
            # Sleep because the BGG API is a bit overzealous with its throttling
            time.sleep(1)
            bgg_plays = bgg.plays(user, min_date=start_date, max_date=end_date)
            if bgg_plays:
                plays[user] = bgg_plays.plays
            store[user] = plays[user]
    return plays

def count_monday_play_sessions(plays):
    """
    Given a dictionary of users and their plays, return a dict of sessions by game.

    This filters out expansions, games that weren't played on a Monday, and
    does some basic deduping if multiple sessions were recorded for the same
    game on the same day, so it's not entirely accurate but probably close
    enough.
    """

    day_tracker = collections.defaultdict(list)
    count = collections.Counter()
    session_list = list(itertools.chain(*plays.values()))
    game_dict = collections.OrderedDict()
    for session in session_list:
        game_data = get_game_data(session.game_id)
        if game_data.expansion:
            continue
        if session.date.weekday() == 0:
            if session.game_id not in game_dict:
                game_dict[session.game_id] = {
                    'count': 0,
                    'sessions': []
                }
            if session.date not in day_tracker[session.game_id]:
                game_dict[session.game_id]['count'] += 1
                game_dict[session.game_id]['game'] = game_data
                game_dict[session.game_id]['sessions'].append(session)
                game_dict[session.game_id]['image'] = get_image_for_game(session.game_id)
                day_tracker[session.game_id].append(session.date)
    game_dict = collections.OrderedDict(sorted(game_dict.items(), key = lambda x: x[1]['game'].name))
    return game_dict

def get_game_data(game_id):
    """ Get BGG data about the given game_id, retrieves from the shelf cache if possible """
    if str(game_id) not in store:
        print("Getting data for game: {0}".format(game_id))
        time.sleep(1)
        store[str(game_id)] = bgg.game(None, game_id=game_id)
    return store[str(game_id)]

def get_image_for_game(game_id):
    """ Download the full image for the given game_id, if it doesn't already exist """
    filename = 'imagecache/{0}.jpg'.format(game_id)
    if os.path.isfile(filename):
        print("Found cached image for game {0}".format(game_id))
        return filename
    game = get_game_data(game_id)
    print ("Downloading image for game {0}".format(game_id))
    response = requests.get('http:{0}'.format(game.image), stream=True)
    with open(filename, 'wb') as out_file:
        shutil.copyfileobj(response.raw, out_file)
        del response
    return filename

def generate_resized_images(sessions):
    """ Generate a bunch of image for all game sessions based on how frequently
    they were played. """
    most_played = max([v['count'] for k, v in sessions.items()])
    resized_images = {}
    for game_id, game_data in sessions.items():
        filename = 'build/images/{0}.jpg'.format(game_id)
        img = Image.open(game_data['image'])
        width = math.log(game_data['count']) / math.log(most_played) * (MAX_IMAGE_WIDTH - IMAGE_WIDTH) + IMAGE_WIDTH
        rounded_width = round(width / IMAGE_WIDTH) * IMAGE_WIDTH
        ratio = img.size[0]/rounded_width
        height = img.size[1]/ratio
        size = (int(rounded_width), int(height))
        img = img.resize(size, resample=Image.LANCZOS)
        img.save(filename, 'JPEG')
        resized_images[game_id] = filename
    return resized_images

if __name__ == "__main__":
    env = Environment(loader=FileSystemLoader('.'))
    bgg = BoardGameGeek()
    store = shelve.open('cache')

    start_date = datetime.date(2014, 1, 1)
    end_date = datetime.date(2014, 12, 31)

    prepare_build()
    plays = get_plays_for_users(SD_USERS, START_DATE, END_DATE)
    sessions = count_monday_play_sessions(plays)
    resized_images = generate_resized_images(sessions)

    template = env.get_template('template.html')
    rendered_template = template.render(sessions=sessions)

    with open("build/index.html", "wb") as fh:
        fh.write(rendered_template.encode('utf-8'))
