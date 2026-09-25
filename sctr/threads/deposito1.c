/* Programa de control del deposito v1

	Compilar con:		gcc deposito1.c -o deposito1 -lpthread -lposix4
	Compilar linux:		gcc deposito1.c -o deposito1 -lpthread -lrt
	
	Ejecutar con: 		./deposito1
*/

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <pthread.h>
#include <unistd.h>

// Declaraci? de prototipos

void * controldep (void *);
void * llenado (void *);
void * alarma  (void *);
void * lanzar (void *);
void * reloj (void *);

// Declaraci? de variable globales

pthread_t start, control, llenar, alar, tempo,thmain;

pthread_attr_t attr;

int volumen, umbral, caudal, caudalvaci, peligro;
unsigned long tiempo, tiempoej;


// Definici? de funciones

void * lanzar (void * arg)
{
	pthread_create (&tempo, &attr, reloj, NULL);
	pthread_create (&control, &attr, controldep,NULL);
	pthread_create (&llenar, &attr, llenado, NULL);
	pthread_create (&alar, &attr, alarma, NULL);
}

void * controldep (void * arg)
{
	while (tiempo<tiempoej)
	{
		if (volumen > umbral)
		{
			volumen = volumen - (caudalvaci);
			printf("Control: he reducido la volumen a %d\n", volumen);
		}
		sleep(2);
	}
}

void * alarma (void * arg)
{
	while (tiempo<tiempoej)
	{
		if (volumen > peligro)
		{
			printf ("Alarma: cuidado, la volumen es %d\n", volumen);
		}
		sleep(1);
	}
}
		
void * llenado (void * arg)
{
	while (tiempo<tiempoej)
	{
	 	volumen =volumen + caudal;
	 	printf("Llenado: volumen = %d \n", volumen);
	 	sleep (1);
	}
}

void * reloj (void * arg)
{
	while (tiempo < tiempoej)
		tiempo++;
	pthread_exit(NULL);
}

int main (void)
{
	tiempo = 0;
	volumen = 0;

	pthread_attr_init (&attr);
	pthread_attr_setscope(&attr,PTHREAD_SCOPE_SYSTEM);
	
	printf("\n Introduce el tiempo de simulacion: ");
	scanf("%lu",  &tiempoej);
	
	tiempoej = tiempoej * 20000000;
	
	printf("\n Introduce el caudal de llenado en litros/seg: ");
	scanf("%d",  &caudal);
	
	printf("\n Introduce el caudal de vaciado en litros/seg: ");
	scanf("%d",  &caudalvaci);
	
	printf("\n Introduce el umbral de control: ");
	scanf("%d",&umbral);
		
	printf("\n Introduce el volumen maximo para activar la alarma: ");
	scanf("%d", &peligro);
	
	pthread_create(&start, &attr, lanzar, NULL);
	
	printf("\n Soy main, he lanzado la ejecucion y salgo\n");
	
	pthread_exit(NULL);
}
	
	
	
