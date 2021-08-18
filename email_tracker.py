import threading
import smtplib

# Import the email modules we'll need
from email.mime.text import MIMEText


from config import env_config
from utils import make_logger


weeks = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class EmailNotifier():
    def __init__(self):
        self.subject = env_config["env"]["title"]
        self.sender = env_config["env"]["sender"]

        self.logger = make_logger("EmailNotifier", "email")

        return

    @staticmethod
    def notify_user(title, rules, users):
        '''
        Notify Users when a CBElement has been changed

        Args:
            title: String, Title of the email.
            rules: List of dictionarys, rules to record in the email content.
            users: List of Strings, the target email addresses to send notifier email.

        Returns:
            None
        '''
        title += "=================================================\n"
        for rule in rules:
            title += email_notifier.rule2msg(rule)
            title += "\n=================================================\n"
        email_notifier.send(users, title)

        return

    @staticmethod
    def rule2msg(rule):
        if rule["mode"] == "Sensor":
            if rule["comparison_open"] != "notset":
                open_str = f" than {rule['threshold_open']}\n"
            else:
                open_str = "\n"
            if rule["comparison_close"] != "notset":
                close_str = f" than {rule['threshold_close']}\n"
            else:
                close_str = "\n"
            msg = (
                f"Actuator {rule['actuator_alias']} switched to Sensor Mode\n"
                f"Sensor : {rule['sensor_alias']}\n"
                f"Open Threshold : {rule['comparison_open']}"
                f"{open_str}"
                f"Close Threshold : {rule['comparison_close']}"
                f"{close_str}"
            )
        elif rule["mode"] == "Timer":
            msg = (
                f"Actuator {rule['actuator_alias']} switched to Timer Mode\n"
                f"Open Timing : {rule['time_open'].strftime('%H:%M:%S')}\n"
                f"Close Timing : {rule['time_close'].strftime('%H:%M:%S')}\n"
            )
        else:
            msg = (
                f"Actuator {rule['actuator_alias']} switched to {rule['mode']} manually\n"
            )
        if rule["mode"] != "ON" and rule["mode"] != "OFF":
            if len(rule["weekday"]):
                msg += f"Weekdays : {EmailNotifier.weekday2msg(rule['weekday'])}\n"
            else:
                msg += "Weekdays: Every day\n"
            if int(rule["duty_pos"]) > 0:
                msg += f"Duty Cycle : Positive Period: {rule['duty_pos']}, Negative Period: {rule['duty_neg']}\n"
            else:
                msg += "Duty Cycle : None\n"
        return msg

    @staticmethod
    def weekday2msg(weekdays):
        days = [int(x) for x in weekdays.split(",")]
        if 7 in days or len(days) == 7:
            return "Every day"
        else:
            msg = ""
            for day in days:
                msg += f"{weeks[day]} "
        return msg

    def get_connection(self):
        self.logger.info("Create SMTP Connection")
        smtp_client = smtplib.SMTP('localhost')
        return smtp_client

    def send(self, dst_list, msg):
        try:
            t = threading.Thread(target=self._send, args=(self, dst_list, msg,))
            t.start()
        except Exception as err:
            self.logger.exception(f"Failed at creating email notifier thread, {err}")

    @staticmethod
    def _send(self, dst_list, msg):
        smtp_client = self.get_connection()
        email_content = MIMEText(msg)
        email_content["Subject"] = self.subject
        email_content['From'] = self.sender
        try:
            smtp_client.sendmail(self.sender, dst_list, email_content.as_string())
            smtp_client.quit()
            for client in dst_list:
                self.logger.info(f"Send email to {client}, MSG: \n{msg}")
            self.logger.info("Quit SMTP Connection")
        except Exception as err:
            self.logger.exception(err)
        return


email_notifier = EmailNotifier()
