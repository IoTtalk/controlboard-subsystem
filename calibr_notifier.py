import smtplib

# Import the email modules we'll need
from email.mime.text import MIMEText


from config import env_config



class CalibrNotifier():
    def __init__(self):
        self.sender = env_config["env"]["sender"]

        return

    def get_connection(self):
        smtp_client = smtplib.SMTP('localhost')
        return smtp_client

    def send(self, dst_list, msg):
        smtp_client = self.get_connection()
        email_content = MIMEText(msg)
        email_content["Subject"] = "Calibration Notice"
        email_content['From'] = self.sender
        try:
            smtp_client.sendmail(self.sender, dst_list, email_content.as_string())
            smtp_client.quit()
        except Exception as err:
            self.logger.exception(err)
        return
        

calibr_notifier = CalibrNotifier()