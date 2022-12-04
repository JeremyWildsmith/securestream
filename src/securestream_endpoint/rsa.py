import itertools
import math
import random
from argparse import ArgumentParser

from egcd import egcd
import json

from .subsystem import Packet
from .crypto import RsaCryptor, save_key

"""
The basis of encryption is a numeric operation that is easy in one direction,
but hard in another.

The discrete logarithm problem forms the basis of this.

1. Consider the below equation
   3^x mod 17 ≡ n
   
   3 is the generator, 17 is the modulus, if both generator and modulus are prime:
   Raising x to any given number will generate a 'n' which is evenly distributed
   between [0, 17); for any given x, n is easy to compute. However, for any given n,
   x is hard to compute.
   
   Therefore f(x)=3^x mod n is easy to compute, but f^-1 is very hard to compute
   
   This is called a one-way function
   
3. RSA Is based off of this premise of a one-way function, except ONE person gets
   a trap-door (enough information to make reverse easy); this trap-door stays private.
   
   a^x ≡ n   (mod c)
   
   How can we leverage this to encrypt a message and expose a trap-door?

4. 
    All numbers have a phi function (eulers totient function), which defines their breakability
        phi(n) is the number of integers k between [1, n] where gcd(k, n) = 1 (ie numbers which do not have a common factor with n)
        phi(4); [1, 4) = 1, 2, 3; common factors with are [2]. len([1,2,3] - [2]) = 2. Therefore phi(4) = 2
        phi(8); [1, 8) = 1,2,3,4,5,6,7; numbers with common factors to 8 are [2, 4, 6]. Remaining is [1, 3, 5, 7]
        phi(n) where n is prime is always (n - 1)
        phi(n*m) = phi(n) * phi(m) if n and m are relatively prime (and two given prime numbers are relatively prime to eachother)
        
    Deriving from step 3, we know that
        n = pq (where p and q are prime)
        - n is hard to factor given p and q are large
        - knowing p and q, it is easy to compute n
    
    In step 4, we build on this to state that
        phi(n) = phi(p) * phi(q)    (where p and q are prime numbers)
        - phi(n) is difficult to compute withput p and q
        
    We now have a one-way function, and can also have a trap-door for reversing this function. How do we apply this for
    cryptograph though?

5.
    Eulers Theorem states:
    m^(phi(n)) ≡ 1   (mod n)
    
    Where m and n are relatively prime to eachother

5a. Using the property that 1^k, for any k, will always equal 1, we introduce a constant into the exponent
    m^(k*phi(n)) ≡ 1  (mod n)
    
5b. We can introduce a message into the equation by multiplying both sides by m
    m*m^(k*phi(n)) ≡ m  (mod n)
    
    eq. 1
        m ^ (k*phi(n) + 1) ≡ m  (mod n)

    This function maps m back onto itself. The key to RSA is breaking the exponent into two parts:
        - public key
        - private key
    
    m ^(pub*priv) = m (mod n)
    
    We can partially complete this transformation by raising m to pub:
        enc = m ^ pub (mod n)
    
        This cannot be easily reversed knowing enc, n and pub but not knowing m (recall point #1)
        THUS it is safely encrypted
        
    We can decrypt the message by completing the transformation
    
    dec = enc^priv  (mod n)
        = ((m ^ pub) ^ priv)   (mod n)
        = m^(pub * priv)       (mod n)
        = m

6. And so the next step is to identify a meaningful way to decompose the exponent into public and private keys.
    ed=(k*phi(n) + 1)
    therefore
    d = (k*phi(n) + 1) / e
    
    - d must be solved for a whole integer, not a rational number    
    - In order for there to exist a number k to satisfy this equation, e must be coprime to phi(n)
    - typically, 'e' is defined as 3, or 65537, since these values have ideal characteristics for performing the
      computations efficiently on hardware.
        - In this case, we actually start with selecting n, and then ensure when generating the prime factors for n (p and q)
          we filter out numbers which are not coprime with e (65537)

6b. We must find a value for k and e. For e, we use 65537
    
    d = (k*phi(n) + 1) / 65537
        ( given phi(n) is coprime with 65537 )
    
    d is equal to the modulo multiplicative inverse of e (mod phi(n))
    
    Which we can compute using the extended Euclidean algorithm
"""

def diffiehellman_keyexchange():
    """
    The deffiehellman key exchange allows us to secretly exchange keys
    between two endpoints, without a MITM attack.
    """

    # The one way function is public and must be easy to compute
    # one way, but hard any other way. For this, we use the discrete
    # logarithmic problem
    modulus = gen_prime(200)

    def f(n, generator=3):
        return (generator ** n) % modulus

    # A generate a random prime number
    a_secret = gen_prime(4)
    b_secret = gen_prime(4)

    # We use the generator to produce a public N using the one-way function
    # defined above.
    a_pub_3 = f(a_secret, generator=3)
    b_pub_3 = f(b_secret, generator=3)

    # A & B can effectively perform the same computation now, without
    # knowing eachother's secret.

    ab_secret = f(a_secret, generator=b_pub_3)
    ba_secret = f(b_secret, generator=a_pub_3)

    if ab_secret == ba_secret:
        print(f"Same secret! {ab_secret}")
    else:
        print("Hmm, something went wrong!")
        print(a_secret)
        print(b_secret)


def is_prime(n, k=10):
    if n % 2 == 0:
        return False
    if n <= 3:
        return True

    # Fermat primality test
    for _ in range(k):
        a = random.randint(2, n - 2)
        # Modulus power (a ** (n - 1) % n)
        if pow(a, n - 1, n) != 1:
            return False

    return True


def is_prime_old(n):
    if n == 1:
        return False
    #
    if n > 2 and n % 2 == 0:
        return False
    #
    # Iterating over root n would find redundant / repeated
    # divisors.
    limit = math.floor(math.sqrt(n))
    #
    # Can skip even numbers greater than 2,
    # since these are also divisible by 2
    for i in range(3, limit + 1, 2):
        if n % i == 0:
            return False
    #
    return True


def gen_prime(sz, additional_filter = None):
    n = 0
    while True:
        n += random.randint(0, 9)
        num_digits = 1 if n == 0 else (math.floor(math.log10(n)) + 1)
        if num_digits >= sz:
            break
        n *= 10
    #
    while True:
        if is_prime(n) and (additional_filter is None or additional_filter(n)):
            break

        n += 1

    return n


def rsa_gen_key():
    # e is explained in more detail later.
    e = 65537

    def coprime_to_e(n):
        return math.gcd(e, n + 1) == 1

    p = gen_prime(100 + random.randint(0, 50), coprime_to_e)
    q = gen_prime(110 + random.randint(0, 50), coprime_to_e)
    n = p * q

    phi_n = (p - 1) * (q - 1)

    d = egcd(e, phi_n)[1] % phi_n

    public_key = {
        "k": e,
        "n": n
    }

    private_key = {
        "k": d,
        "n": n
    }

    return public_key, private_key

    #def encrypt(pubk, data):
    #    return pow(data, pubk["e"], pubk["n"])
    #
    #def decrypt(privk, data):
    #    return pow(data, privk["d"], privk["n"])

    #r = decrypt(private_key, encrypt(public_key, 82))
    #print(r)

def rsagen_main():
    #diffiehellman_keyexchange()

    parser = ArgumentParser(
        prog='keygen',
        description='Generates a public and private key file, and places them in the working "'
                    'directory ./private.key and ./public.key')

    public, private = rsa_gen_key()

    save_key("public.key", public["k"], public["n"])
    save_key("private.key", private["k"], private["n"])


if __name__ == "__main__":
    rsagen_main()
