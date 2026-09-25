/* Programa de control del deposito v2: incluye mutex, tiempo de reloj y cambio de prioridad

	Compilar con:		gcc deposito4.c tiempo.c -o deposito4 -lpthread -lposix4
	Compilar linux:		gcc deposito4.c tiempo.c -o deposito4 -lpthread -lrt
	
	Ejecutar con: 		./deposito4
*/


#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

#include "tiempo.h"

#define HIGHPRIORITY 10

// Declaracion de prototipos

void * controldep (void *);
void * llenado (void *);
void * alarma  (void *);
void * lanzar (void *);
void * reloj (void *);

//Declaracion de mutex

static pthread_mutex_t candado;

// Declaracion de variable globales

pthread_t start, control, llenar, alar, tempo,thmain;

pthread_attr_t attr, attr2;

struct sched_param param;

int volumen, umbral, caudal, caudalvaci, peligro;
long tiempo, tiempoej;


// Definicion de funciones

void * lanzar (void * arg)
{
	pthread_create (&control, &attr, controldep,NULL);
	pthread_create (&llenar, &attr, llenado, NULL);
	pthread_create (&alar, &attr2, alarma, NULL);	// prioridad alta
	pthread_create (&tempo, &attr, reloj, NULL);
	
	pthread_exit(NULL);
}

void * controldep (void * arg)
{
	while (tiempo<tiempoej)
	{
		pthread_mutex_lock(&candado);
		if (volumen > umbral)
		{
			volumen = volumen - (caudalvaci);
			printf("Control: he reducido la volumen a %d\n", volumen);
		}
		pthread_mutex_unlock(&candado);
		SLEEP_MSEC(2000);
	}
	pthread_exit(NULL);
}

void * alarma (void * arg)
{
	while (tiempo<tiempoej)
	{
		pthread_mutex_lock(&candado);
		if (volumen > peligro)
			printf ("Alarma: cuidado, la volumen es %d\n", volumen);
		pthread_mutex_unlock(&candado);
		SLEEP_MSEC(1000);
	}
	pthread_exit(NULL);
}
		
void * llenado (void * arg)
{
	while (tiempo<tiempoej)
	{
		pthread_mutex_lock(&candado);
	 	volumen =volumen + caudal;
	 	pthread_mutex_unlock(&candado);
	 	printf("Llenado: volumen = %d \n", volumen);
		SLEEP_MSEC(2000);
	}
	pthread_exit(NULL);
}

void* reloj(void *arg)
{
	while (tiempo < tiempoej)
	{
		SET_TMP();	// lectura de tiempo de reloj
		tiempo = SEC_TRANS();
	}
	
	pthread_exit(NULL);
}
		
		


int main (void)
{
	pthread_mutex_init(&candado, NULL);
	pthread_attr_init (&attr);
	pthread_attr_init (&attr2);
	
	if(pthread_attr_setschedpolicy (&attr, SCHED_FIFO))
		perror("No puedo cambiar el planificador"); 
	if(pthread_attr_setschedpolicy (&attr2, SCHED_FIFO))
		perror("No puedo cambiar el planificador"); 

	// configura attr con alta prioridad
	  if (pthread_attr_getschedparam(&attr2, &param))
			perror ("No puedo obtener los par�metros");
	  else
	  {
		param.sched_priority = HIGHPRIORITY;
		if (pthread_attr_setschedparam(&attr2, &param))
			perror("No puedo cambiar la prioridad");
	  }

	tiempo = 0;
	volumen = 0;
		
  	printf("\n Introduce el tiempo de simulacion: ");
  	scanf("%lu",&tiempoej);

  	printf("\n Introduce el caudal de llenado en litros/seg: ");
  	scanf("%d",&caudal);

  	printf("\n Introduce el caudal de vaciado en litros/seg: ");
  	scanf("%d",&caudalvaci);

  	printf("\n Introduce el umbral de control: ");
  	scanf("%d",&umbral);

  	printf("\n Introduce el volumen maximo para activar la alarma: ");
  	scanf("%d",&peligro);
  		
	
	RESET_TMP();	// inicializa el contador del reloj
	
	pthread_create(&start, &attr, lanzar, NULL);
	
	printf("\n Soy main, he lanzado la ejecucion y salgo\n");
	
	pthread_exit(NULL);
}
	
	
	
