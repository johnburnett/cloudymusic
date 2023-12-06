import json
import os

from itunesLibrary import library
import spotipy


SPOTIFY_SECRETS_FILE_NAME = 'spotify_secrets.json'


debug = print


def authenticate():
    this_dir = os.path.dirname(__file__)
    secrets_file_path = os.path.join(this_dir, SPOTIFY_SECRETS_FILE_NAME)
    with open(secrets_file_path) as fp:
        secrets = json.load(fp)

    secrets_keys = (
        'client_id',
        'client_secret',
        'redirect_uri',
    )
    for key in secrets_keys:
        value = secrets.get(key)
        assert value
        env_key = 'SPOTIPY_' + key.upper()
        os.environ[env_key] = value

    creds = spotipy.oauth2.SpotifyClientCredentials(
        # cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path='.spotipy_auth_cache')
        cache_handler=spotipy.cache_handler.MemoryCacheHandler()
    )
    client = spotipy.Spotify(client_credentials_manager=creds)
    return client


def test_itunes():
    lib_path = os.path.join(os.getenv("USERPROFILE"), "Music/iTunes/iTunes Music Library.xml")
    lib_path = r"C:\Users\john\Downloads\Library_test.xml"
    lib = library.parse(lib_path)

    debug(f'Loaded {len(lib)} items from "{lib_path}"')

    for item in [list(lib)[50]]:
        if item.getItunesAttribute('Track Type') != 'File':
            debug(f'skipping {item}, not a file')
            continue
        if item.getItunesAttribute('Kind') != 'AAC audio file':
            debug(f'skipping {item}, not an AAC audio file')
            continue
        if item.getItunesAttribute('Genre') == 'Podcast':
            debug(f'skipping {item}, is a podcast')
            continue

        title = item.getItunesAttribute('Name')
        artist = item.getItunesAttribute('Artist')
        album_artist = item.getItunesAttribute('Album Artist')
        album = item.getItunesAttribute('Album')

        print(f'{title=}')
        print(f'{artist=}')
        print(f'{album_artist=}')
        print(f'{album=}')


def test_spotipy(client):
    birdy_uri = 'spotify:artist:2WX2uTcsvV5OnS0inACecP'
    results = client.artist_albums(birdy_uri, album_type='album')
    albums = results['items']
    while results['next']:
        results = client.next(results)
        albums.extend(results['items'])

    for album in albums:
        print(album['name'])


client = authenticate()
test_spotipy(client)
