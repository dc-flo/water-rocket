#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>

Adafruit_BMP280 bmp;
Adafruit_MPU6050 mpu;

const char* ssid = "ESP32-Access-Point";
WiFiServer server(80);
String header;

bool is_rec = false;
unsigned long rec_start = 0;
byte rec_time = 20;
byte rps = 100;
int max_values = rps * rec_time * 10;
float vals[20000];
unsigned short i = 0;

void setup() {
  Serial.begin(115200);

  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip");
  }
  Serial.println("MPU6050 Found!");

  if (!bmp.begin(0x76)) {
    Serial.println("Could not find a valid BMP280 sensor, check wiring!");
  }
  Serial.println("BME280 Found!");

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  Serial.print("Setting AP (Access Point)…");
  WiFi.softAP(ssid);
  delay(100);
  WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1), IPAddress(255, 255, 255, 0));
  IPAddress IP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(IP);

  server.begin();
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    Serial.println("New Client.");
    String currentLine = "";
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();
        Serial.write(c);
        header += c;
        if (c == '\n') {
          if (currentLine.length() == 0) {
            client.println("HTTP/1.1 200 OK");
            client.println("Content-type:text/csv");
            client.println("Connection: close");
            client.println();

            if (header.indexOf("GET /start") >= 0) {
              if (header.indexOf("rec_time=") == -1) {
                rec_time = 20;
              } else {
                rec_time = getParam("rec_time=").toInt();
              }
              if (header.indexOf("rps=") == -1) {
                rps = 100;
              } else {
                rps = getParam("rps=").toInt();
              }
              memset(vals, 0, sizeof(vals));
              i = 0;
              Serial.println("started recording");
              rec_start = millis();
              is_rec = true;
            } else if (header.indexOf("GET /get") >= 0) {
              client.println("time,accX,accY,accZ,rotX,rotY,rotZ,temp1,temp2,press");
              for (short row = 0; row < max_values; row = row + 10) {
                for (byte column = 0; column < 10; column++) {
                  if (column < 9) {
                    client.print(vals[row + column]);
                    client.print(",");
                  } else {
                    client.println(vals[row + column]);
                  }
                }
              }
            }
            client.println();
            break;
          } else {
            currentLine = "";
          }
        } else if (c != '\r') {
          currentLine += c;
        }
      }
    }
    header = "";
    client.stop();
    Serial.println("Client disconnected.");
    Serial.println("");
  }

  if (is_rec && waitInterval(rec_start, 1000 / rps)) {
    saveVals();
    if (i / rps / 10 >= rec_time) {
      is_rec = false;
      Serial.println("finished rec");
    }
  }
}

void saveVals() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  vals[i] = millis();
  i++;
  vals[i] = a.acceleration.x;
  i++;
  vals[i] = a.acceleration.y;
  i++;
  vals[i] = a.acceleration.z;
  i++;
  vals[i] = g.gyro.x;
  i++;
  vals[i] = g.gyro.y;
  i++;
  vals[i] = g.gyro.z;
  i++;
  vals[i] = temp.temperature;
  i++;
  vals[i] = bmp.readTemperature();
  i++;
  vals[i] = bmp.readPressure();
  i++;
}

bool waitInterval(unsigned long &expireTime, unsigned long timePeriod) {
  unsigned long currentMillis = millis();
  if (currentMillis - expireTime >= timePeriod) {
    expireTime = currentMillis;
    return true;
  }
  else return false;
}

String getParam(String key) {
  String s = header.substring(header.indexOf(key));
  s.remove(0, key.length());
  if (s.indexOf("&") != -1) {
    s = s.substring(0, s.indexOf("&"));
  } else {
    s = s.substring(0, s.indexOf(" "));
  }
  return s;
}
