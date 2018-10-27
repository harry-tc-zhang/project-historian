## Project Historian

Project Historian is a software tool that aims to automatically generate news timelines from news archives. It was developed with journalists in mind, with the goal of assisting them in background research and storytelling with richer context. It uses natural language processing technologies to discover news stories related to a certain topic and then group them according to thematic similarity.

This project was originally developed as my master's project at Columbia Journalism School.

You can see a demo [here](http://www.projecthistorian.org), although it will need some maintenance as I have graduated a while ago.

To set this up on your own system, follow these steps:

1. Clone the repository and `cd` to it.
2. Install the require packages by running `pip3 install -r requirements.txt`.
3. Set up `cron` jobs for `project_historian/rss_data/cache_rss_db.py`, `project_historian/run_phrase.py` and `project_historian/run_fasttext.py`, in that order. Ideally they should be run once a day during a time when you are unlikely to be using it, such as 4:00 am. They should be sufficiently far apart (e.g. 10 to 20 minutes) to allow the previous task to finish.
4. Let the `cron` jobs run at least once (or you can run the scrips manually yourself once).
5. Start the server with `. project_historian_server/run.sh`, then go to `http://localhost:5000` to see it in action.
