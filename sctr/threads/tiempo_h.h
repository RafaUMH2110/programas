#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

#include <time.h>
#include <sys/time.h>
#include <sys/resource.h>

// Macros
#define RESET_TMP()		clock_gettime(CLOCK_REALTIME, &TIEMPO_time1)	// marca de tiempo 1
#define SET_TMP()		clock_gettime(CLOCK_REALTIME, &TIEMPO_time2)	// marca de tiempo 2

#define SEC_TRANS()		(TIEMPO_time2.tv_sec - TIEMPO_time1.tv_sec)		// segundos transcurridos
#define NSEC_TRANS()	(TIEMPO_time2.tv_nsec - TIEMPO_time1.tv_nsec)	// nanosegundos transcurridos

#define RESET_TIEMPO_rsc()		getrusage(RUSAGE_SELF, &TIEMPO_rsc1)
#define SET_TIEMPO_rsc()		getrusage(RUSAGE_SELF, &TIEMPO_rsc2)

// suspende el thread durante 'ret' milisegundos (puede despertarse por una se�al)
#define SLEEP_MSEC(ret)	{ TIEMPO_retardo.tv_sec= (long)ret/1000; TIEMPO_retardo.tv_nsec= ((long)ret%1000)*1E6; nanosleep (&TIEMPO_retardo, NULL);	}


// Prototipos Funciones
void  VER_TMP(char *txt);
void  VER_RSC(char *txt);

// Variables Globales
struct timespec  TIEMPO_time1, TIEMPO_time2;
struct rusage  TIEMPO_rsc1, TIEMPO_rsc2;
struct timespec  TIEMPO_retardo;




// Funciones
void VER_TMP(char *txt)
{
	if (txt!=NULL)
		fprintf(stderr, "%s ", txt);

	fprintf(stderr, "[Tiempo consumido real: %2.9fs]\n",
			SEC_TRANS() + (float) NSEC_TRANS() * 1E-9 );
}


void VER_RSC(char *txt)
 {
	 int page_size;

	if (txt!=NULL)
		fprintf(stderr, "%s\n", txt);
	page_size=getpagesize();

	fprintf(stderr, "-------------------------------------------------------------\n");
	fprintf(stderr, "Tiempo consumido (usuario): %2.6f   segundos.\n",	
			(TIEMPO_rsc2.ru_utime.tv_sec - TIEMPO_rsc1.ru_utime.tv_sec)
		    +(float)(TIEMPO_rsc2.ru_utime.tv_usec - TIEMPO_rsc1.ru_utime.tv_usec)*1E-6);	
	fprintf(stderr, "Tiempo consumido (sistema): %2.6f   segundos.\n",
			(TIEMPO_rsc2.ru_stime.tv_sec - TIEMPO_rsc1.ru_stime.tv_sec)
		    +(float)(TIEMPO_rsc2.ru_stime.tv_usec - TIEMPO_rsc1.ru_stime.tv_usec)*1E-6);	

	fprintf(stderr, "-------------------------------------------------------------\n");
	
	fprintf(stderr, "ru_nvcsw:   %4lu  -> Cambios de Contexto voluntarios.\n",
				TIEMPO_rsc2.ru_nvcsw);
	fprintf(stderr, "ru_nivcsw:  %4lu  -> Cambios de Contexto involuntarios.\n",
				TIEMPO_rsc2.ru_nivcsw);
	fprintf(stderr, "ru_nswap:   %4lu  -> Swaps (caché de memoria del proceso en HD).\n", 
				TIEMPO_rsc2.ru_nswap);
	fprintf(stderr, "-------------------------------------------------------------\n");

	fprintf(stderr, "ru_inblock: %4lu  -> Operaciones de entrada bloqueadas.\n",
				TIEMPO_rsc2.ru_inblock);
	fprintf(stderr, "ru_oublock: %4lu  -> Operaciones de salida bloqueadas.\n",
				TIEMPO_rsc2.ru_oublock);
	fprintf(stderr, "ru_msgsnd:  %4lu  -> Mensajes enviados.\n",
				TIEMPO_rsc2.ru_msgsnd);
	fprintf(stderr, "ru_msgrcv:  %4lu  -> Mensajes recibidos.\n",
				TIEMPO_rsc2.ru_msgrcv);
	fprintf(stderr, "ru_nsignals:%4lu  -> Señales recibidas.\n",
				TIEMPO_rsc2.ru_nsignals);
	fprintf(stderr, "-------------------------------------------------------------\n");

}
