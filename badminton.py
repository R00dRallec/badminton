import datetime
import logging
import os
import pickle
import socket

import telegram

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

MONDAY = 7  # Offset for calculation of next monday's date via timedelta
FRIDAY = 4  # Offset for calculation of next friday's date via timedelta


def store(data, filename='badminton.pickle'):
    """Stores the given data as dump in the file identified by filename."""
    logging.info('Storing data in %s', filename)
    with open(filename, 'wb') as handle:
        pickle.dump(data, handle)


def load(filename='badminton.pickle'):
    """Loads and returns a stored dump identified by filename."""
    logging.info('Loading data from %s', filename)
    try:
        with open(filename, 'rb') as handle:
            data = pickle.load(handle)
            return data
    except FileNotFoundError:
        logging.debug('Could not find %s', filename)
        return {}


def get_next_date(weekday, date=None):
    """ Returns the next date of the upcoming weekday after the given date."""
    if date is None:
        date = datetime.date.today()
    next_date = date + datetime.timedelta(days=(weekday - date.weekday()))
    return next_date


class PersistentData:
    """Class representing the persistent data to be stored
    related to Badminton polls."""

    def __init__(self, poll_message_id=None, poll_id=None, polling_date=None):
        self.poll_message_id = poll_message_id
        self.poll_id = poll_id
        self.polling_date = polling_date

    def get_poll_message_id(self):
        return self.poll_message_id

    def get_poll_id(self):
        return self.poll_id

    def get_polling_date(self):
        return self.polling_date

    def set_poll_message_id(self, poll_message_id):
        self.poll_message_id = poll_message_id

    def set_poll_id(self, poll_id):
        self.poll_id = poll_id

    def set_polling_date(self, polling_date):
        self.polling_date = polling_date


class BadmintonBot:
    """Badminton Bot for automatic poll creation and evaluation."""

    def __init__(self, token, group_id):
        self.bot = telegram.Bot(token=token)
        self.group_id = group_id

        self.data = load('poll.data')
        if isinstance(self.data, dict):
            self.data = PersistentData()
            store(self.data, 'poll.data')

    def send_message(self, message):
        """Sends a message to the given group."""
        try:
            self.bot.send_message(self.group_id, message)
        except socket.timeout as timeout:
            logging.info('Caught exception %s', str(timeout))

    def send_poll(self, question, options=None):
        """Sends a poll to the given chat."""
        message_id = None
        poll_id = None
        if options is None:
            options = ['Ja', 'Nein']
        try:
            message = self.bot.send_poll(self.group_id, question, options=options, is_anonymous=False)
            message_id = message.message_id
            poll_id = message.poll.id
        except socket.timeout as timeout:
            logging.info('Caught exception %s', str(timeout))

        return message_id, poll_id

    def evaluate_poll(self, message_id, poll_id, options=None):
        """Evaluates the latest results from a poll."""
        # Stop the Poll, i.e. close it
        self.bot.stop_poll(self.group_id, message_id)

        # Get all other updates for evaluation of exact voting results per user
        updates = self.get_updates(-100)

        if options is None:
            options = ['Ja', 'Nein']

        # Check all updates to get per-user poll results
        for update in updates:
            if update.poll_answer is not None:
                poll_answer = update.poll_answer
                if poll_id == poll_answer.poll_id:
                    print("User {} {} voted {}".format(poll_answer.user.first_name, poll_answer.user.last_name, options[poll_answer.option_ids[0]]))

    def get_updates(self, update_id=None):
        """Returns all updates for the bot since the last update."""
        updates = []
        try:
            if update_id is not None:
                logging.info('Last update ID %d', update_id)
                updates = self.bot.get_updates(update_id)
            else:
                logging.info('No update ID found, retrieving all updates')
                updates = self.bot.get_updates()
        except socket.timeout as timeout:
            logging.info('Caught exception %s', str(timeout))

        return updates

    def get_latest_updates(self):
        """Gets the latest updates based on the stored update_id and updates
        the update_id itself accordingly. """
        update_id = load('update.id')
        updates = self.get_updates(update_id)
        update_id = updates[-1].update_id
        store(update_id, 'update.id')

    def manage_badminton_poll(self):
        """Manages Badminton polls.
        Creates a new poll if required and evaluates an ongoing one the friday
        before the target date."""

        if self.data.get_polling_date() is None:
            # There is no pending poll, create a new one.
            next_monday = get_next_date(MONDAY)
            logging.info('Create new poll for %s', str(next_monday))
            message_id, poll_id = bot.send_poll("Abfrage {}".format(str(next_monday)))
            self.data.set_poll_message_id(message_id)
            self.data.set_poll_id(poll_id)
            self.data.set_polling_date(next_monday)
        elif datetime.date.today() == get_next_date(FRIDAY, self.data.get_polling_date()):
            # Poll was already created, we can evaluate it now, as we are at the friday before the event.
            logging.info('Evaluate poll from %s', str(self.data.get_polling_date()))
            self.evaluate_poll(self.data.get_poll_message_id(), self.data.get_poll_id())
            # Reset data
            self.data = PersistentData()
        else:
            # A poll has already been created, but we still have time to gather all responses
            logging.info("Nothing to evaluate yet...")

        # We can always store the persistent data, as it will be updated accordingly in every case.
        store(self.data, 'poll.data')


if __name__ == '__main__':
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    GROUP_ID = os.environ.get('GROUP_ID')
    if BOT_TOKEN is None or GROUP_ID is None:
        print("Environment variables 'BOT_TOKEN' and 'GROUP_ID' must be set")
        exit(-1)
    bot = BadmintonBot(BOT_TOKEN, GROUP_ID)
    bot.manage_badminton_poll()
