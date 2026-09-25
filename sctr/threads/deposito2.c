/* Programa de control del deposito v2: incluye mutex

	Compilar con:		gcc deposito2.c -o deposito2 -lpthread -lposix4
	Compilar linux:		gcc deposito2.c -o deposito2 -lpthread -lrt
	
	Ejecutar con: 		./deposito2
*/


#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

void *controldep ( void *);
void *llenado ( void *);
void *alarma ( void *);
void *lanzar ( void *);
void *reloj ( void *);

pthread_t start, control, llenar, alar, tempo, thmain;
pthread_attr_t attr;
pthread_mutex_t candado;

int volumen,umbral,caudal,caudalvaci,peligro;
unsigned long tiempo,tiempoej;

void *lanzar ( void *arg)
{
	 pthread_create(&tempo,&attr,reloj,NULL);
	 pthread_create(&control,&attr,controldep,NULL);
	 pthread_create(&llenar,&attr,llenado,NULL);
	 pthread_create(&alar,&attr,alarma,NULL);

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
		sleep(2);
	}
	pthread_exit(NULL);
}

void * alarma (void * arg)
{
	while (tiempo<tiempoej)
	{
		pthread_mutex_lock(&candado);
		if (volumen > peligro)
		{
			printf ("Alarma: cuidado, la volumen es %d\n", volumen);
		}
		pthread_mutex_unlock(&candado);
		sleep(1);
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
		sleep(1);
	}
	pthread_exit(NULL);
}

		
void * reloj (void * arg)
{
	while (tiempo < tiempoej)
		tiempo++;
	pthread_exit(NULL);
}

	 
int main(void)
{
  tiempo=0;
  volumen=0;

  pthread_attr_init(&attr);
  pthread_mutex_init(&candado,NULL);
  pthread_attr_setscope(&attr,PTHREAD_SCOPE_SYSTEM);

  printf("\n Introduce el tiempo de simulacion: ");
  scanf("%lu",&tiempoej);
  tiempoej=tiempoej*20000000;

  printf("\n Introduce el caudal de llenado en litros/seg: ");
  scanf("%d",&caudal);

  printf("\n Introduce el caudal de vaciado en litros/seg: ");
  scanf("%d",&caudalvaci);

  printf("\n Introduce el umbral de control: ");
  scanf("%d",&umbral);

  printf("\n Introduce el volumen maximo para activar la alarma: ");
  scanf("%d",&peligro);
  
  pthread_create(&start,&attr,lanzar,NULL);
  printf("\n soy main, he lanzado la ejecucion y salgo");

  pthread_exit(NULL);
}








