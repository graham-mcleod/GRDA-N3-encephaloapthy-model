TITLE nap.mod
 
COMMENT
 Persistent (as opposed to regular) sodium current for pyramidal cell and interneurons defined in
 Timofeev et. al., 2000, Cerebral Cortex (https://doi.org/10.1093/cercor/10.12.1185) 
 and Bazhenov et. al. 2002 (J Neuro) and 
 Chen et. al., 2012, J. Physiol. (doi:  https://doi.org/10.1113/jphysiol.2012.227462)
 This code is adapted from hh.mod distributed with NEURON source code
ENDCOMMENT
 
UNITS {
        (mA) = (milliamp)
        (mV) = (millivolt)
	(S) = (siemens)
}
 
? interface
NEURON {
        SUFFIX nap
        USEION na READ ena WRITE ina
        RANGE gnabar
        RANGE minf, mtau
}
 
PARAMETER {
        gnabar = .00007 (S/cm2)	<0,1e9>
        mtau = 0.1991501863698107 (ms)	<0,1e9> :see Krishnan 2016 currents.h lines 544-545
        ena = 50 (mV)
}
 
STATE {
        m
}
 
ASSIGNED {
        v (mV)
        :celsius (degC)

	gna (S/cm2)
        ina (mA/cm2)
        minf
}
 
? currents
BREAKPOINT {
        SOLVE states METHOD cnexp
        gna = gnabar*m
	ina = gna*(v - ena)
}
 
 
INITIAL {
	rates(v)
	m = minf
}

? states
DERIVATIVE states {  
        rates(v)
        m' =  (minf-m)/mtau
}
 
? rates
PROCEDURE rates(v(mV)) {  :Computes rate and other constants at current v.
                      :Call once from HOC to initialize inf at resting v.
UNITSOFF
                :"m" sodium activation system
        minf = 1/(1 + exp(-(v+42)/5))
UNITSON
}



