# HTTPS Setup Options

## Option 1: Self-Signed Certificate (Demo/Dev)
```python
# Add to compute_stack.py imports
from aws_cdk import aws_certificatemanager as acm

# In _create_application_load_balancer method, add after ALB creation:
# Create self-signed certificate for demo
self.certificate = acm.Certificate(
    self,
    "SelfSignedCert",
    domain_name=f"*.{self.env_name}.local",
    validation=acm.CertificateValidation.from_dns(),
)

# Add HTTPS listener
self.https_listener = self.alb.add_listener(
    "HTTPSListener",
    port=443,
    protocol=elbv2.ApplicationProtocol.HTTPS,
    certificates=[self.certificate],
    default_action=elbv2.ListenerAction.forward([self.target_group_1]),
)

# Redirect HTTP to HTTPS
self.listener.default_action = elbv2.ListenerAction.redirect(
    protocol="HTTPS",
    port="443",
    permanent=True
)
```

## Option 2: Real Certificate (Production)
```python
# If you have a domain, use:
self.certificate = acm.Certificate.from_certificate_arn(
    self, "Certificate", 
    certificate_arn="arn:aws:acm:region:account:certificate/cert-id"
)
```

## Option 3: Keep HTTP for Now
- Current setup works for demo
- Add HTTPS when you have a real domain
- Focus on other improvements first