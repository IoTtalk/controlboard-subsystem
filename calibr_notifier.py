calibr_notifier.py
未共用
類型
文字
大小
857 個位元組
儲存空間使用量
857 個位元組
位置
ca
擁有者
我
上次修改時間
我在2021年1月21日修改過
上次開啟時間
我在下午4:24開啟過
建立日期
下午4:19 (使用「Google Drive Web」建立)
新增說明
檢視者可以下載
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