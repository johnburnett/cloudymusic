import json
import os
import plistlib
import re
import sys

import spotipy


SPOTIFY_SECRETS_FILE_NAME = 'spotify_secrets.json'

AUDIO_KINDS = {
    'AAC audio file',
    'MPEG audio file',
    'Purchased AAC audio file',
}

VIDEO_KINDS = {
    'MPEG-4 video file',
    'Protected MPEG-4 video file',
    'Purchased MPEG-4 video file',
    'QuickTime movie file',
}


def fatal(msg):
    print(f'ERROR: {msg}')
    sys.exit(1)


def warn(msg):
    print(f'WARNING: {msg}')


info = print


def debug(msg):
    print(f'DEBUG: {msg}')


# def debug(msg):
#     pass


def authenticate(scopes=None):
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

    # creds = spotipy.oauth2.SpotifyClientCredentials(
    #     # cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path='.spotipy_auth_cache')
    #     cache_handler=spotipy.cache_handler.MemoryCacheHandler()
    # )
    # client = spotipy.Spotify(client_credentials_manager=creds)

    client = spotipy.Spotify(auth_manager=spotipy.oauth2.SpotifyOAuth(scope=scopes))

    return client


def iter_itunes_tracks(library_path):
    with open(library_path, mode='rb') as fp:
        library = plistlib.load(fp, fmt=plistlib.FMT_XML)
    tracks = library.get('Tracks', {})
    debug(f'Loaded {len(tracks)} tracks from "{library_path}"')

    for track_id, track in sorted(tracks.items()):
        if track.get('Track Type') != 'File':
            debug(f'skipping track {track_id}, not a file')
            continue
        kind = track.get('Kind')
        if kind in VIDEO_KINDS:
            debug(f'skipping track {track_id}, is a video')
            continue
        assert kind in AUDIO_KINDS
        if track.get('Genre') == 'Podcast':
            debug(f'skipping track {track_id}, is a podcast')
            continue

        yield {
            'album': track.get('Album'),
            'album_artist': track.get('Album Artist'),
            'artist': track.get('Artist'),
            'rating': track.get('Album Rating'),
            'title': track.get('Name'),
        }


def simplify_album_name(album):
    match = re.search(r'(?P<album>.*) \(?Dis[ck] \d+\)?', album)
    if match:
        return match['album'].rstrip()
    match = re.search(r'(?P<album>.*) \(?Volume \d+\)?', album)
    if match:
        return match['album'].rstrip()
    return album


def simplify_artist_name(artist):
    return artist.replace("'", "")


def test_spotipy(client):
    birdy_uri = 'spotify:artist:2WX2uTcsvV5OnS0inACecP'
    results = client.artist_albums(birdy_uri, album_type='album')
    albums = results['items']
    while results['next']:
        results = client.next(results)
        albums.extend(results['items'])

    for album in albums:
        print(album['name'])


def test_find_albums():
    library_path = os.path.join(os.getenv("USERPROFILE"), "Music/iTunes/iTunes Music Library.xml")

    found_album_uris = []
    missing_albums = []

    client = authenticate()
    searched_queries = set()
    for ii, track in enumerate(iter_itunes_tracks(library_path)):
        album = track['album']
        simplified_album = simplify_album_name(album)
        album_artist = track['album_artist']

        query = f'artist:{album_artist} album:{simplified_album}'
        if query in searched_queries:
            continue
        searched_queries.add(query)
        result = client.search(q=query, type='album')
        # with open('c:/t/json.json', 'w') as fp:
        #     json.dump(result, fp, indent=2)
        # debug(result)

        items = result.get('albums', {}).get('items')
        if items:
            album = items[0]
            album_uri = album['uri']
            album_name = album['name']
            album_artist_uris = [artist['uri'] for artist in album['artists']]
            album_artist_names = [artist['name'] for artist in album['artists']]
            info(f'Found album: {album_name=} ({album_artist_names=})')
            found_album_uris.append(album_uri)
        else:
            missing_albums.append({'album': album, 'album_artist': album_artist})
            warn(f'No album found named "{album}" for artist "{album_artist}"')

    data = dict(found_album_uris=found_album_uris, missing_albums=missing_albums)
    with open('albums.json', 'w') as fp:
        json.dump(data, fp, indent=2)


def test_find_artists():
    library_path = os.path.join(os.getenv("USERPROFILE"), "Music/iTunes/iTunes Music Library.xml")

    found_artist_uris = []
    missing_artists = []

    client = authenticate()
    searched_queries = set()
    for ii, track in enumerate(iter_itunes_tracks(library_path)):
        for artist_name in set((track['album_artist'], track['artist'])):
            simplified_artist_name = simplify_artist_name(artist_name)
            query = f'artist:{simplified_artist_name}'
            if query in searched_queries:
                continue
            searched_queries.add(query)
            result = client.search(q=query, type='artist')
            # with open('c:/t/json.json', 'w') as fp:
            #     json.dump(result, fp, indent=2)
            # debug(result)

            items = result.get('artists', {}).get('items')
            if items:
                artist = items[0]
                artist_uri = artist['uri']
                info(f'Found artist "{artist_name}"')
                found_artist_uris.append(artist_uri)
            else:
                missing_artists.append(artist_name)
                warn(f'No artist found named "{artist_name}"')

    data = dict(found_artist_uris=found_artist_uris, missing_artists=missing_artists)
    with open('artists.json', 'w') as fp:
        json.dump(data, fp, indent=2)


if __name__ == '__main__':
    try:
        test_find_artists()
    except KeyboardInterrupt:
        pass
