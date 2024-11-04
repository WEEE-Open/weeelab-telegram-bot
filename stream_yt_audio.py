# this script does the same as:
# cvlc https://www.youtube.com/watch?v=hHW1oY26kxQ (uses dummy interface for video but still outputs many errors)
from time import time

import youtube_dl
import vlc  # python-vlc when installing with pip
from time import sleep


class LofiVlcPlayer:
    def __init__(self):
        self.player = None
        self.playurl = None
        self.last_player_time = None
        pass

    def player_exist(self):
        return self.player is not None

    def get_player(self):
        if self.player is None:
            self.__create_new_player()
        elif (
            not self.player.is_playing() and int(time()) > self.last_player_time + 3600
        ):
            self.player.release()  # TODO: how do we close this thing?
            self.__create_new_player()
        return self.player

    def __create_new_player(self):
        playurl = self.__get_playurl()
        instance = vlc.Instance("-q")
        player = instance.media_player_new()
        media = instance.media_new(playurl)
        media.get_mrl()  # TODO: what does this do?
        player.set_media(media)
        player.audio_set_volume(70)
        self.player = player
        return player

    def __get_playurl(self):
        if self.last_player_time is None:
            self.__download_metadata()
        elif time() > self.last_player_time + 300:
            self.__download_metadata()
        return self.playurl

    def __download_metadata(self):
        self.last_player_time = time()
        # lofi hip hop radio - beats to relax/study to by ChilledCow
        url = "https://www.youtube.com/watch?v=5qap5aO4i9A"
        # https://stackoverflow.com/a/49249893
        ydl_opts = {
            "format": "bestaudio/best",
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            playurl = info["formats"][0]["url"]
        self.playurl = playurl
        self.last_player_time = time()


if __name__ == "__main__":
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
