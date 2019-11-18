# this script does the same as:
# cvlc https://www.youtube.com/watch?v=hHW1oY26kxQ (uses dummy interface for video but still outputs many errors)

import youtube_dl
import vlc  # python-vlc when installing with pip
from time import sleep


class LofiVlcPlayer:
    def __init__(self):
        self.player = None
        pass

    def get_player(self):
        if self.player is None:
            return self.__create_new_player()
        else:
            return self.player

    def __create_new_player(self):
        # lofi hip hop radio - beats to relax/study to by ChilledCow
        url = "https://www.youtube.com/watch?v=hHW1oY26kxQ"
        # https://stackoverflow.com/a/49249893
        ydl_opts = {
            'format': 'bestaudio/best',
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            playurl = info['formats'][0]['url']
        instance = vlc.Instance('-q')
        player = instance.media_player_new()
        media = instance.media_new(playurl)
        media.get_mrl()
        player.set_media(media)
        player.audio_set_volume(50)
        self.player = player
        return player


if __name__ == '__main__':
    # to test if streaming works
    # player = LofiVlcPlayer().get_player()
    # player.play()
    # sleep(5)
    # player.stop()

    # to test if endless streaming works
    # player = LofiVlcPlayer().get_player()
    # player.play()
    # while True:
    #     pass

    # to test if volume change works
    player = LofiVlcPlayer().get_player()
    player.play()
    variation = -10
    while True:
        print("VLC Volume:", player.audio_get_volume())
        sleep(5)
        player.audio_set_volume(player.audio_get_volume() + variation)
        if player.audio_get_volume() == 0 or player.audio_get_volume() == 100:
            variation = -variation

    # to test start and stop
    # player = LofiVlcPlayer().get_player()
    # player.play()
    # while True:
    #     if player.is_playing():
    #         sleep(10)
    #         player.stop()
    #     else:
    #         sleep(5)
    #         player.play()

# player.stop()  #-- to stop/end video
# player.is_playing() # 1 if True, 0 if False

# these 2 only work for non-live streaming video:
# player.pause() #-- to pause video
# player.resume()  #-- resume paused video.
