#include <AccelStepper.h>    //Libreria para el uso del motor paso a paso NEMA17
#include <Servo.h>    //Libreria para el uso del servomotor (filtros)

// Pines DRV8825
const int dirPin = 3;
const int stepPin = 4;
const int slpPin = 5;
const int rstPin = 6;
const int enPin = 7;
const int M0Pin = 8;
const int M1Pin = 9;
const int M2Pin = 10;
const int ledPin = 11;
const int limitSwitchPin = 12;

// Servo
const int pinServo = 2;
int pulsomin = 500;
int pulsomax = 2440;
Servo miServo;    //Creacion del objeto servomotor

// Configuración motor paso a paso
const int stepsPerRevolution = 200;
const int microSteps = 16;
const float rev = microSteps * stepsPerRevolution;
int factorVel = 5;
float vel = rev * 0.1 * factorVel;
const long maxSteps = 93000;    //Limite maximo de movimiento

int motorDirection = 0;
bool motorActivo = false;

int ledIntensity = 5;
bool ledEncendido = false;

bool homingDone = false;

AccelStepper motor(AccelStepper::DRIVER, stepPin, dirPin);    //Creacion del objeto motor paso a paso 

void setup() {
  delay(2000);

  // Pines DRV8825
  pinMode(slpPin, OUTPUT);
  pinMode(rstPin, OUTPUT);
  pinMode(enPin, OUTPUT);
  pinMode(M0Pin, OUTPUT);
  pinMode(M1Pin, OUTPUT);
  pinMode(M2Pin, OUTPUT);
  pinMode(ledPin, OUTPUT);
  pinMode(limitSwitchPin, INPUT_PULLUP);

  digitalWrite(rstPin, HIGH);
  digitalWrite(enPin, HIGH);
  digitalWrite(slpPin, HIGH);

  digitalWrite(M0Pin, LOW); 
  digitalWrite(M1Pin, LOW);
  digitalWrite(M2Pin, HIGH);

  analogWrite(ledPin, 0);    //Iniciar con el LED apagado

  motor.setMaxSpeed(1000 * microSteps);

  // Servo
  miServo.attach(pinServo, pulsomin, pulsomax);
  miServo.write(0); // Posición inicial: CLEAR

  Serial.begin(115200);

  hacerHoming();    //Siempre que se inicia el programa se hace un homing para comenzar en la posicion 0

  /*

  El dispositivo funciona mediante el envio de comandos mediante el puerto serial de Arduino

  Lista de comandos

  r: Movimiento continuo a la derecha (hacia la lente)
  l: Movimiento continuo a la izquierda
  s: Detener cuando se activa alguno de los dos comandos anteriores
  v#: Definir la velocidad a la que se quiere que el motor opere, seleccionar valores de 1 a 10, siendo 10 la velocidad mas alta
  p###f: Ir un numero de pasos deseados desde el punto donde esta hacia adelante (hacia la lente)
  p###b: Ir un numero de pasos deseados desde el punto donde esta hacia atras
      En ambos casos si el numero de pasos exceden los limites, tanto antes del punto 0 (home) como
      mas alla del punto maximo (93000 pasos) el movimiento no se ejecutara
  on: Encender el LED
  off: Apagar el LED
  led#: Definir la intensidad del LED, toma valores de 1 a 10 siendo 10 la intensidad maxima del LED
  g#: Mueve la pantalla a una posicion deseada en pasos
      En este caso no se especifica una direccion de movimiento ya que el movimiento puede ser adelante
      o hacia atras dependiendo de en que lugar se encuentre la pantalla en el momento, si la posicion
      deseada excede los limites de movimiento, por ejemplo, 'g95000' el movimiento no se ejecutara
  f:x: Mueve la paleta de filtros a un filtro deseado 
      f:w ---> activa el filtro white o clear, es decir, no hay filtro alguno
      f:r ---> activa el filtro rojo
      f:g ---> activa el filtro verde
      f:b ---> activa el filtro azul
  */
  Serial.println("Iniciado con exito.");
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command.startsWith("v")) {
      factorVel = command.substring(1).toInt();

    } else if (command == "r") {
      if (motor.currentPosition() < 0) {
        motorDirection = 1;
        motor.setSpeed(abs(vel * factorVel)); 
        activarMotor(true);
      } else {
        motorDirection = 0;
        activarMotor(false);
      }

    } else if (command == "l") {
      if (motor.currentPosition() > -maxSteps) {
        motorDirection = -1;
        motor.setSpeed(-abs(vel * factorVel)); 
        activarMotor(true);
      } else {
        motorDirection = 0;
        activarMotor(false);
      }

    } else if (command == "s") {
      motorDirection = 0;
      motor.setSpeed(0);
      activarMotor(false);

    } else if (command.startsWith("p")) {
      long steps = command.substring(1, command.length() - 1).toInt();
      char direction = command.charAt(command.length() - 1);

      activarMotor(true);

      if (direction == 'f') {
        if (motor.currentPosition() + steps <= 0) {
          moveSteps(steps, 1);
        }
      } else if (direction == 'b') {
        if (motor.currentPosition() - steps >= -maxSteps) {
          moveSteps(steps, -1);
        }
      }

      activarMotor(false);

    } else if (command == "on") {
      ledEncendido = true;
      analogWrite(ledPin, map(ledIntensity, 1, 10, 25, 255));

    } else if (command == "off") {
      ledEncendido = false;
      analogWrite(ledPin, 0);

    } else if (command.startsWith("led")) {
      int nivel = command.substring(3).toInt();
      if (nivel >= 1 && nivel <= 10) {
        ledIntensity = nivel;
        if (ledEncendido) {
          analogWrite(ledPin, map(nivel, 1, 10, 25, 255));
        }
      }

    } else if (command.startsWith("g")) {
      long objetivo = command.substring(1).toInt();
      if (objetivo >= 0 && objetivo <= maxSteps) {
        long destino = -objetivo;
        moverAPosicion(destino);
      }

    } else if (command.startsWith("f:")) {
      char filtro = command.charAt(2);
      moverFiltro(filtro);
    }
  }

  // Control continuo del motor
  if (motorDirection != 0) {
    long pos = motor.currentPosition();
    if ((motorDirection == 1 && pos < 0) ||
        (motorDirection == -1 && pos > -maxSteps)) {
      motor.runSpeed();
    } else {
      motorDirection = 0;
      motor.setSpeed(0);
      activarMotor(false);
    }
  }

  // Imprimir posición actual
  static unsigned long lastPrintTime = 0;
  unsigned long now = millis();
  if (now - lastPrintTime > 200) {
    Serial.print("POS: ");
    Serial.println(motor.currentPosition());
    lastPrintTime = now;
  }
}


//Funcion para mover una serie de pasos deseados en una direccion
void moveSteps(long steps, int direction) {
  long posicionInicial = motor.currentPosition();
  long posicionDestino = posicionInicial + (direction * steps);

  if (posicionDestino > 0 || posicionDestino < -maxSteps) {return;}

  motor.setSpeed(direction * vel * factorVel);

  while ((direction == 1 && motor.currentPosition() < posicionDestino) ||
         (direction == -1 && motor.currentPosition() > posicionDestino)) {
    motor.runSpeed();
  }

  motor.setSpeed(0);
  Serial.print("POS: ");
  Serial.println(motor.currentPosition());
}

//Funcion para mover a una posicion deseada absoluta
void moverAPosicion(long destino) {
  long actual = motor.currentPosition();

  if (destino > 0 || destino < -maxSteps) {return;}

  if (destino == actual) {return;}

  activarMotor(true);

  int direccion = (destino < actual) ? -1 : 1;
  motor.setSpeed(direccion * vel * factorVel);

  //Serial.print("Moviendo de ");
  //Serial.print(actual);
  //Serial.print(" a ");
  //Serial.println(destino);

  while ((direccion == 1 && motor.currentPosition() < destino) ||
         (direccion == -1 && motor.currentPosition() > destino)) {
    motor.runSpeed();
  }

  motor.setSpeed(0);
  activarMotor(false);

  //Serial.print("Posición final alcanzada: ");
  Serial.println(motor.currentPosition());
}

//Funcion para cambiar los filtros
void moverFiltro(char filtro) {
  int angulo = 0;

  switch (filtro) {
    case 'w': angulo = 0; break;
    case 'r': angulo = 57; break;
    case 'g': angulo = 120; break;
    case 'b': angulo = 180; break;
    default:
      return;
  }

  miServo.write(angulo);
  Serial.print("Filtro cambiado a: ");
  Serial.println(filtro);
}


//Funcion para activar y desactivar el motor mediante el uso de la funcion Enable del driver DRV8825
void activarMotor(bool activo) {
  if (activo != motorActivo) {
    digitalWrite(enPin, activo ? LOW : HIGH);
    motorActivo = activo;
    delay(5);
  }
}


//Funcion para hacer el homing cuando se inicia el dispositivo
void hacerHoming() {
  Serial.println("Iniciando Homing...");
  activarMotor(true);  
  motor.setSpeed(rev * 0.2);

  while (digitalRead(limitSwitchPin) == HIGH) {
    motor.runSpeed();
  }

  motor.setSpeed(0);
  delay(200);
  motor.setCurrentPosition(0);

  motor.setSpeed(-vel);
  long target = motor.currentPosition() - 554;

  /* long target = motor.currentPosition() - valor
  
  Este valor es la cantidad de pasos que se le dice al motor que se mueva
  cuando se presiona el sensor de final de carrera, entre mas alto el valor 
  mas alejado del sensor de final de carrera va a mover el motor, 
  ajustelo dependiendo de como el sensor de final de carrera va cambiando
  de sensibilidad
  */

  while (motor.currentPosition() > target) {
    motor.runSpeed();
  }

  motor.setCurrentPosition(0);
  Serial.println("Homing completado. Posición actual: 0");
  homingDone = true;
  activarMotor(false); 
}