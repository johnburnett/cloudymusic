import json
import os
import plistlib
import re
import sys

import spotipy


SPOTIFY_SECRETS_FILE_NAME = 'spotify_secrets.json'
SPOTIFY_MAX_PLAYLIST_COUNT = 10_000

ITUNES_AUDIO_KINDS = {
    'AAC audio file',
    'MPEG audio file',
    'Purchased AAC audio file',
}
ITUNES_VIDEO_KINDS = {
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


def debug(msg):
    print(f'DEBUG: {msg}')
    pass


info = print


def chunked(items, max_chunk_size):
    index = 0
    while index < len(items):
        yield items[index : index + max_chunk_size]
        index += max_chunk_size


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


def dump(data):
    with open('c:/t/json.json', 'w') as fp:
        json.dump(data, fp, indent=2)
    debug(data)


################################################################################
# iTunes


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
        if kind in ITUNES_VIDEO_KINDS:
            debug(f'skipping track {track_id}, is a video')
            continue
        assert kind in ITUNES_AUDIO_KINDS
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


################################################################################
# Spotify


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

    cache_root_path = '.'
    kwargs = {}
    if scopes:
        cache_path = os.path.join(cache_root_path, '.spotipy_user_auth_cache')
        cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=cache_path)
        auth_manager = spotipy.oauth2.SpotifyOAuth(scope=scopes, cache_handler=cache_handler)
        kwargs = dict(auth_manager=auth_manager)
    else:
        cache_path = os.path.join(cache_root_path, '.spotipy_auth_cache')
        cache_handler = spotipy.cache_handler.CacheFileHandler(cache_path=cache_path)
        cred_manager = spotipy.oauth2.SpotifyClientCredentials(cache_handler=cache_handler)
        kwargs = dict(client_credentials_manager=cred_manager)

    client = spotipy.Spotify(**kwargs)
    return client


def iter_paged_items(client, results):
    while True:
        for item in results['items']:
            yield item
        if results['next']:
            results = client.next(results)
        else:
            break


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
    with open('spotify_albums.json', 'w') as fp:
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
    with open('spotify_artists.json', 'w') as fp:
        json.dump(data, fp, indent=2)


def test_make_playlist():
    client = authenticate(scopes=['playlist-modify-public'])
    user = client.current_user()
    user_id = user.get('id') if user else None

    with open('spotify_albums.json') as fp:
        data = json.load(fp)
    album_uris = data.get('found_album_uris', [])

    playlist_base_name = 'iTunes Import'
    playlist_count = 1
    playlist_track_count = 0
    playlist = client.user_playlist_create(user_id, playlist_base_name)
    for ii, album_uri in enumerate(album_uris):
        debug(f'Adding album {ii + 1} of {len(album_uris)} ({album_uri})')
        result = client.album_tracks(album_uri)
        all_album_tracks = [track['uri'] for track in iter_paged_items(client, result)]

        assert len(all_album_tracks) <= SPOTIFY_MAX_PLAYLIST_COUNT
        if (playlist_track_count + len(all_album_tracks)) > SPOTIFY_MAX_PLAYLIST_COUNT:
            playlist_count += 1
            playlist = client.user_playlist_create(
                user_id, f'{playlist_base_name} {playlist_count}'
            )
            playlist_track_count = 0
        playlist_track_count += len(all_album_tracks)

        for album_tracks in chunked(all_album_tracks, 100):
            client.playlist_add_items(playlist['id'], album_tracks)


def test_save_albums():
    with open('spotify_albums.json') as fp:
        data = json.load(fp)
    album_uris = data.get('found_album_uris', [])

    client = authenticate(scopes=['user-library-read', 'user-library-modify'])
    chunk_size = 20  # per Spotify docs
    for chunk_index, album_uris_chunk in enumerate(chunked(album_uris, chunk_size)):
        start_index = chunk_index * chunk_size + 1
        end_index = chunk_index * chunk_size + chunk_size
        info(f'Adding albums {start_index} - {end_index}...')
        client.current_user_saved_albums_add(album_uris_chunk)


if __name__ == '__main__':
    try:
        test_save_albums()
    except KeyboardInterrupt:
        pass
