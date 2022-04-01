#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#include <WebServer.h>
#include <Adafruit_BME280.h>

#define ONBOARD_LED 2

Adafruit_BMP280 bmp;
Adafruit_BME280 bme;
short bm = 0;
Adafruit_MPU6050 mpu;

const char* ssid = "ESP32-Access-Point";
const char* password = "WR2022";

IPAddress local_ip(192,168,1,1);
IPAddress gateway(192,168,1,1);
IPAddress subnet(255,255,255,0);
WebServer server(80);

bool is_rec = false;
unsigned long rec_start = 0;
byte rec_time = 20;
byte rps = 100;
int max_values = rps * rec_time * 10;
float vals[20000];
unsigned short i = 0;
float rotX = 0;
float rotY = 0;
float rotZ = 0;

unsigned long stream_start = 0;

void handle_get(){
  String v = "time,accX,accY,accZ,rotX,rotY,rotZ,temp1,temp2,press\n";
  for (short row = 0; row < max_values; row = row + 10) {
    short sum = 0;
    for (byte column = 0; column < 10; column++) {
      sum += vals[row + column];
    }
    if(sum == 0) goto stop;
    for (byte column = 0; column < 10; column++) {
      if (column < 9) {
        v += vals[row + column];
        v += ",";
      } else {
        v += vals[row + column];
        v += "\n";
      }
    }
  }
  stop:
  server.send(200, "text/csv", v);
}

void handle_start(){
  rec_time = 20;
  rps = 100;
  for(char j = 0; j < server.args(); j++){
    if(server.argName(j) == "rec_time"){
      rec_time = server.arg(j).toInt();
    }
    if(server.argName(j) == "rps"){
      rps = server.arg(j).toInt();
    }
  }
  memset(vals, 0, sizeof(vals));
  i = 0;
  Serial.print("started recording: ");
  Serial.print(rec_time);
  Serial.print(" - ");
  Serial.println(rps);
  rec_start = millis();
  is_rec = true;
  digitalWrite(ONBOARD_LED, HIGH);
  char buf[100];
  sprintf(buf, "recording for %d seconds with %d rps", rec_time, rps);
  server.send(200, "text/plain", buf);
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
  if(bm == 0){
    vals[i] = bmp.readTemperature();
    i++;
    vals[i] = bmp.readPressure();
    i++;
  } else if (bm ==1) {
    vals[i] = bme.readTemperature();
    i++;
    vals[i] = bme.readPressure();
    i++;
  } else {
    vals[i] = -1;
    i++;
    vals[i] = -1;
    i++;
  }
}

bool waitInterval(unsigned long &expireTime, unsigned long timePeriod) {
  unsigned long currentMillis = millis();
  if (currentMillis - expireTime >= timePeriod) {
    expireTime = currentMillis;
    return true;
  }
  else return false;
}

void setup() {
  Serial.begin(9600);
  Wire.begin();

  pinMode(ONBOARD_LED,OUTPUT);

  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip");
  }
  Serial.println("MPU6050 Found!");

  if (!bmp.begin(0x76)) {
    Serial.println("bmp280 not found, try bme280");
    bm++;
    if(!bme.begin(0x76)){
      Serial.println("Could not find a valid BME280 sensor, check wiring!");
      bm++;
    }
  }
  Serial.println("BME280 Found!");

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  Serial.print("Setting AP (Access Point)…");
  WiFi.softAP(ssid, password);
  delay(100);
  WiFi.softAPConfig(local_ip, gateway, subnet);
  IPAddress IP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(IP);

  server.on("/get", handle_get);
  server.on("/start", handle_start);

  server.begin();

  delay(100);

  stream_start = millis();
}

void loop() {
  server.handleClient();

  if (is_rec && waitInterval(rec_start, 1000 / rps)) {
    saveVals();
    if (i / rps / 10 >= rec_time) {
      is_rec = false;
      digitalWrite(ONBOARD_LED, LOW);
      Serial.println("finished rec");
    }
  }
  if(waitInterval(stream_start, 500)) {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  rotX += g.gyro.x * 0.5 * 180/PI;
  rotY += g.gyro.y * 0.5 * 180/PI;
  rotZ += g.gyro.z * 0.5 * 180/PI;

  Serial.print("Acceleration X: ");
  Serial.print(a.acceleration.x);
  Serial.print(", Y: ");
  Serial.print(a.acceleration.y);
  Serial.print(", Z: ");
  Serial.print(a.acceleration.z);
  Serial.println(" m/s^2");

  Serial.print("Rotation X: ");
  Serial.print(rotX);
  Serial.print(", Y: ");
  Serial.print(rotY);
  Serial.print(", Z: ");
  Serial.print(rotZ);
  Serial.println(" rad/s");

  Serial.print("Temperature: ");
  Serial.print(temp.temperature);
  Serial.println(" degC");

  Serial.println("");
  }
}