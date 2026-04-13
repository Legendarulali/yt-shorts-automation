# schema-5-yt

A python script used to automate short content.

Comes with a downloader that uses deno for faster downloading and resolving all of the json problems (requires GET COOKIES locally bc after a certain amount of downloaded clips youtube stops bc thinks that you are a bot; the session is limited and it will expire after a certain period of time. All of the downloaded videos are in .av1 format for saving space.

The main script uses a secondary script called render_utils.py.

The secondary script draws the main text on the screen and outlines the curent word that is being spoken by the voice in the background; besides that it creates a loading line that will make the viewer aware how much is being left on the short. It also generates secondary text for the subscribe button and for the like button for a short period of time.

The main script uses Whisper from OpenAi and MoviePy to: 
                1. Auto resize the long form video from 16:9 (landscape) to short content 9:16 (portrait) 
                2. Has an dictionary for autocorecting words that can be mistakenly understood by Whisper (it is not perfect at the end of the day but gets the job done) 
                3. Before rendering the short, it first transcribe the video in a .json file for the user to verify that there are no mistakes in spelling and after the user check that every word is spelled correctly user must press enter for the script to continue and strat rendering the short.

!!ATENTION!! 
THE SCRIPT WAS CREATED FOR THE AMD GPU BUT IT IS ALSO COMPATIBLE WITH THE NVIDIA GPU. THE USER MUST CHANGE AT LINE 124 WITH THE COMMENTS ON LINE 123 AND AT LINE 159 WITH THE COMMENTS ON LINE 158
