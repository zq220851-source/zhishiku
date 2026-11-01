"""Linear 24-to-16 kHz PCM conversion for synthetic service checks only."""
from array import array
import sys

def pcm_24k_to_16k(data):
    samples=array('h');samples.frombytes(data)
    if sys.byteorder!='little':samples.byteswap()
    output=array('h')
    for i in range(len(samples)*2//3):
        n=i*3;left=n//2
        output.append(samples[left] if n%2==0 or left+1==len(samples) else (samples[left]+samples[left+1])//2)
    if sys.byteorder!='little':output.byteswap()
    return output.tobytes()
