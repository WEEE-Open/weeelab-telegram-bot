# this script does the same as:
# cvlc https://www.youtube.com/watch?v=hHW1oY26kxQ (uses dummy interface for video but still outputs many errors)

import pafy  # pip dependency for backend: youtube-dl
import vlc  # python-vlc when installing with pip
from time import sleep


def get_lofi_vlc_player():
    # lofi hip hop radio - beats to relax/study to by ChilledCow
    url = "https://www.youtube.com/watch?v=hHW1oY26kxQ"
    video = pafy.new(url)
    playurl = video.getbest().url

    instance = vlc.Instance()
    player = instance.media_player_new()
    media = instance.media_new(playurl)
    media.get_mrl()
    player.set_media(media)
    return player

# to test if streaming works
# player = get_lofi_vlc_player()
# player.play()
# sleep(5)
# player.stop()

# to test if endless streaming works
# player = get_lofi_vlc_player()
# player.play()
# while True:
#     sleep(1)

# to test start and stop
# player = get_lofi_vlc_player()
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