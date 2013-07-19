chan chan_warn= [0] of {byte};
chan chan_connection= [0] of {byte};
chan chan_attemptcalc= [0] of {byte};
chan chan_log= [0] of {byte};
chan chan_verificationprocess = [1] of {byte};
chan chan_imageprocessor = [1] of {byte};
chan chan_sessionkeygathering = [1] of {byte};
chan chan_credentials = [1] of {byte};
chan chan_encryption = [1] of {byte};
chan chan_comparison = [1] of {byte};
chan chan_thirdpartyverification = [1] of {byte};
chan chan_analysis = [1] of {byte};
chan chan_interfacepreparation = [1] of {byte};
chan chan_interfaceshow = [1] of {byte};
chan chan_alert = [1] of {byte};
byte result,setparamsout,temp,usercredentials,fakeinterface,biometrictemplate,fakeinterfacetemplate,wrongattemptno,hasheddata,biometricimage,sessionkey,userinfo,verificationlog,analysisresult,parameters,encrypteddata;

byte fake;

typedef features {
	bool Offline_1;
	bool Setparams_2;
	bool Userinfo_1;
	bool Defaultparams;
	bool Sesionkey;
	bool Biometricprocessing_1;
	bool Fakeenabled_1;
	bool Defaultparams_2;
	bool Setparams;
	bool Online_1
};
features f;
active proctype userverification(){
	chan_verificationprocess!userinfo;
	{
		chan_verificationprocess?userinfo;
	};
	{
		gd
		:: f.Biometricprocessing_1-> 
			chan_imageprocessor!biometricimage;
			chan_imageprocessor?biometrictemplate;
		:: else -> skip;
		dg;
		gd
		:: f.Sesionkey-> 
			byte tempI;
			chan_sessionkeygathering!tempI;
			chan_sessionkeygathering?sessionkey;
		:: else -> skip;
		dg;
		gd
		:: f.Userinfo_1-> 
			byte tempI;
			chan_credentials!tempI;
			chan_credentials?usercredentials;
		:: else -> skip;
		dg;
	};
	{
		gd
		:: f.Defaultparams_2-> 
			chan_encryption!usercredentials;
			chan_encryption?encrypteddata;
		:: else -> skip;
		dg;
		gd
		:: f.Setparams_2-> temp=1; 
			{
				chan_encryption!parameters;
				chan_encryption?setparamsout;
			};
			{
				byte tempI;
				chan_encryption!tempI;
				chan_encryption?encrypteddata;
			};
		:: else -> skip;
		dg;
	};
	{
		gd
		:: f.Offline_1-> temp=1; 
			{
				byte tempI;
				chan_encryption!tempI;
				chan_encryption?encrypteddata;
			};
			{
				chan_comparison!encrypteddata;
				chan_comparison?result;
			};
		:: else -> skip;
		dg;
		gd
		:: f.Online_1-> temp=1; 
			{
				chan_thirdpartyverification!hasheddata;
			};
			{
				chan_thirdpartyverification?result;
			};
		:: else -> skip;
		dg;
	};
	{
		gd
		:: f.Fakeenabled_1-> temp=1; 
			{
				chan_analysis!encrypteddata;
				chan_analysis?analysisresult;
			};
			{
				if
				:: (analysisresult == fake) -> 
					chan_interfacepreparation!userinfo;
					chan_interfacepreparation?fakeinterfacetemplate;
					skip;
					byte tempI;
					chan_interfaceshow!tempI;
					chan_interfaceshow?fakeinterface;
					byte tempR;
					chan_alert!tempR;
					skip;
				fi;
			};
		:: else -> skip;
		dg;
	};
}