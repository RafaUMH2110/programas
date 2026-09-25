/*-------------------------------------------------------------
	Cabecera para la medida de tiempo de forma precisa 
		tiempo.h
  -------------------------------------------------------------*/

#ifndef __TIEMPO_H__
#define __TIEMPO_H__

#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <sys/time.h>
#include <sys/resource.h>

// Macros
#define RESET_TMP()		clock_gettime(CLOCK_REALTIME, &TIEMPO_time1)
#define SET_TMP()		clock_gettime(CLOCK_REALTIME, &TIEMPO_time2)

#define SEC_TRANS()		(TIEMPO_time2.tv_sec - TIEMPO_time1.tv_sec)		// segundos transcurridos
#define NSEC_TRANS()	(TIEMPO_time2.tv_nsec - TIEMPO_time1.tv_nsec)		// nanosegundos transcurridos

#define RESET_RSC()		getrusage(RUSAGE_SELF, &TIEMPO_rsc1)
#define SET_RSC()		getrusage(RUSAGE_SELF, &TIEMPO_rsc2)

// suspende el thread durante 'ret' milisegundos (puede despertarse por una señal)
#define SLEEP_MSEC(ret)	{ TIEMPO_retardo.tv_sec= (long)ret/1000; TIEMPO_retardo.tv_nsec= ((long)ret%1000)*1E6; nanosleep (&TIEMPO_retardo, NULL);	}

// Prototipos Funciones
void  VER_TMP(char *txt);
void  VER_RSC(char *txt);

// Variables Globales
extern struct timespec  TIEMPO_time1, TIEMPO_time2;
extern struct rusage  TIEMPO_rsc1, TIEMPO_rsc2;
extern struct timespec  TIEMPO_retardo;

#endif

