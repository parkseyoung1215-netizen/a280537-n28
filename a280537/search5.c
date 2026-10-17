// No-four-coplanar in the cube [n]^3: valid-only random add/remove local search.
// Usage: ./search4 n seconds seed outfile [target]
// Keeps the set always valid (no 4 coplanar, no 3 collinear).
// blocked[c] = number of (pair lines + triple planes) of the current set passing through cell c.
// A cell is "free" iff blocked[c]==0 and not selected: adding it keeps the set valid.
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static int n, N;
static int *blocked; static char *sel;
static int S[4096], K = 0, pos[1 << 16];
static int X[1 << 16], Y[1 << 16], Z[1 << 16];
static long long *tabu;
static unsigned long long rng;
static inline unsigned long long xr(void){ rng^=rng<<13; rng^=rng>>7; rng^=rng<<17; return rng; }
static int gcd(int a,int b){ if(a<0)a=-a; if(b<0)b=-b; while(b){int t=a%b;a=b;b=t;} return a; }
static inline int id(int x,int y,int z){ return (x*n+y)*n+z; }

static void line(int a,int b,int sgn){
  int dx=X[b]-X[a],dy=Y[b]-Y[a],dz=Z[b]-Z[a]; int g=gcd(gcd(dx,dy),dz); dx/=g;dy/=g;dz/=g;
  int x=X[a],y=Y[a],z=Z[a];
  while(x-dx>=0&&x-dx<n&&y-dy>=0&&y-dy<n&&z-dz>=0&&z-dz<n){x-=dx;y-=dy;z-=dz;}
  while(x>=0&&x<n&&y>=0&&y<n&&z>=0&&z<n){ blocked[id(x,y,z)]+=sgn; x+=dx;y+=dy;z+=dz; }
}
static void plane(int a,int b,int c,int sgn){
  int ux=X[b]-X[a],uy=Y[b]-Y[a],uz=Z[b]-Z[a], vx=X[c]-X[a],vy=Y[c]-Y[a],vz=Z[c]-Z[a];
  int nx=uy*vz-uz*vy, ny=uz*vx-ux*vz, nz=ux*vy-uy*vx;
  int g=gcd(gcd(nx,ny),nz); if(!g) return; nx/=g;ny/=g;nz/=g;
  int D=nx*X[a]+ny*Y[a]+nz*Z[a];
  int ax=abs(nx),ay=abs(ny),az=abs(nz);
  if(az>=ax&&az>=ay){ for(int i=0;i<n;i++)for(int j=0;j<n;j++){int v=D-nx*i-ny*j; if(v%nz==0){int t=v/nz; if(t>=0&&t<n) blocked[id(i,j,t)]+=sgn;}} }
  else if(ay>=ax){ for(int i=0;i<n;i++)for(int j=0;j<n;j++){int v=D-nx*i-nz*j; if(v%ny==0){int t=v/ny; if(t>=0&&t<n) blocked[id(i,t,j)]+=sgn;}} }
  else { for(int i=0;i<n;i++)for(int j=0;j<n;j++){int v=D-ny*i-nz*j; if(v%nx==0){int t=v/nx; if(t>=0&&t<n) blocked[id(t,i,j)]+=sgn;}} }
}
static void apply(int p,int sgn){  // add (+1) or remove (-1) the structures created by p with the rest of S
  for(int i=0;i<K;i++){ int q=S[i]; if(q==p) continue; line(p,q,sgn);
    for(int j=i+1;j<K;j++){ int r=S[j]; if(r==p) continue; plane(p,q,r,sgn); } }
}
static void addp(int p){ apply(p,+1); sel[p]=1; pos[p]=K; S[K++]=p; }
static void remp(int p){ sel[p]=0; int k=pos[p]; int q=S[--K]; S[k]=q; pos[q]=k; apply(p,-1); }

static void save(const char *fn){ FILE *f=fopen(fn,"w"); if(!f) return; fprintf(f,"%d %d\n",n,K);
  for(int i=0;i<K;i++) fprintf(f,"%d %d %d\n",X[S[i]],Y[S[i]],Z[S[i]]); fclose(f); }

int main(int argc,char**argv){
  if(argc<5){fprintf(stderr,"usage: n seconds seed outfile [startK]\n");return 1;}
  n=atoi(argv[1]); double secs=atof(argv[2]); rng=strtoull(argv[3],0,10)*2654435761ULL+99991; const char*out=argv[4];
  int startK = argc>5? atoi(argv[5]) : 0;
  N=n*n*n; blocked=calloc(N,sizeof(int)); sel=calloc(N,1); tabu=calloc(N,sizeof(long long));
  for(int x=0;x<n;x++)for(int y=0;y<n;y++)for(int z=0;z<n;z++){int c=id(x,y,z);X[c]=x;Y[c]=y;Z[c]=z;}
  clock_t t0=clock(); long long it=0; int best=0;
  // phase 1: greedy valid build
  for(;;){ int nf=0,pick=-1; for(int c=0;c<N;c++) if(!sel[c]&&blocked[c]==0){ nf++; if(xr()%nf==0) pick=c; }
    if(pick<0) break; addp(pick); }
  best=K; save(out); fprintf(stderr,"greedy K=%d\n",K);
  if(startK>K) while(K<startK){ int bc=-1,bv=1<<30,t=0; for(int c=0;c<N;c++) if(!sel[c]){ int v=blocked[c]; if(v<bv){bv=v;bc=c;t=1;} else if(v==bv&&xr()%(++t)==0) bc=c; } addp(bc); }
  // phase 2: fixed-K min-conflicts with tabu; on success K++
  for(;;){
    if((it&63)==0 && (double)(clock()-t0)/CLOCKS_PER_SEC>secs) break;
    it++;
    long long off=(long long)(K-1)*(K-2)/2+(K-1); long long V=0; int rp=-1; long long bv=-1; int t=0;
    for(int i=0;i<K;i++){ int p=S[i]; long long v=blocked[p]-off; V+=v; if(tabu[p]>it) continue;
      if(v>bv){bv=v;rp=p;t=1;} else if(v==bv&&xr()%(++t)==0) rp=p; }
    if(V==0){ if(K>best){best=K;save(out);fprintf(stderr,"[%.0fs] K=%d (it=%lld)\n",(double)(clock()-t0)/CLOCKS_PER_SEC,K,it);}
      int bc=-1,cv=1<<30; t=0; for(int c=0;c<N;c++) if(!sel[c]){int v=blocked[c]; if(v<cv){cv=v;bc=c;t=1;} else if(v==cv&&xr()%(++t)==0) bc=c;}
      addp(bc); continue; }
    if(rp<0||(xr()%100)<5) rp=S[xr()%K];
    remp(rp); tabu[rp]=it+5+(long long)(xr()%(K/3+3));
    int bc=-1,cv=1<<30; t=0;
    for(int c=0;c<N;c++) if(!sel[c]&&tabu[c]<=it){int v=blocked[c]; if(v<cv){cv=v;bc=c;t=1;} else if(v==cv&&xr()%(++t)==0) bc=c;}
    if(bc<0) bc=rp;
    addp(bc); tabu[bc]=it+3+(long long)(xr()%(K/3+3));
  }
  printf("n=%d best=%d iters=%lld\n",n,best,it);
  return 0;
}
