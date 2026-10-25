from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BasePage:
    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, 10)

    def open(self, path=""):
        self.driver.get(f"{self.base_url}{path}")
        return self

    def find(self, by, value):
        return self.wait.until(EC.visibility_of_element_located((by, value)))

    def type(self, by, value, text):
        el = self.find(by, value)
        el.clear()
        el.send_keys(text)

    def click(self, by, value):
        self.wait.until(EC.element_to_be_clickable((by, value))).click()

    def flash(self, kind):
        return self.find(By.ID, f"flash-{kind}").text

    @property
    def path(self):
        return self.driver.current_url.replace(self.base_url, "").split("?")[0]

    def logout(self):
        self.click(By.ID, "logout-link")

    def welcome(self):
        return self.find(By.ID, "welcome").text
