import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Privacy Policy – Fazle AI',
  description: 'Privacy Policy for Fazle AI platform',
};

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold">Fazle AI</Link>
          <nav className="flex gap-4 text-sm">
            <Link href="/terms-services" className="text-muted-foreground hover:text-foreground transition-colors">Terms of Service</Link>
            <Link href="/login" className="text-muted-foreground hover:text-foreground transition-colors">Login</Link>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Privacy Policy</h1>
        <p className="text-sm text-muted-foreground mb-10">Last updated: March 21, 2026</p>

        <div className="prose prose-neutral dark:prose-invert max-w-none space-y-8">
          {/* 1 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">1. Introduction</h2>
            <p className="leading-relaxed text-muted-foreground">
              Fazle AI (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) is committed to protecting your privacy. This Privacy
              Policy explains how we collect, use, disclose, and safeguard your information when you use
              the Fazle AI platform and related services (collectively, the &quot;Services&quot;). Please read this
              Privacy Policy carefully. By using our Services, you consent to the practices described in
              this policy.
            </p>
          </section>

          {/* 2 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">2. Information We Collect</h2>
            <p className="leading-relaxed text-muted-foreground">We may collect the following types of information:</p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li><strong className="text-foreground">Account Information:</strong> Name, email address, and credentials you provide when creating an account.</li>
              <li><strong className="text-foreground">Usage Data:</strong> Information about how you interact with our Services, including pages visited, features used, and actions taken.</li>
              <li><strong className="text-foreground">Device Information:</strong> Browser type, operating system, IP address, and device identifiers.</li>
              <li><strong className="text-foreground">Content Data:</strong> Any content, messages, or data you submit through the platform, including inputs to AI systems.</li>
              <li><strong className="text-foreground">Integration Data:</strong> Information from third-party platforms you connect, such as WhatsApp or Facebook, including API tokens and page identifiers.</li>
            </ul>
          </section>

          {/* 3 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">3. How We Use Information</h2>
            <p className="leading-relaxed text-muted-foreground">We use the collected information to:</p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li>Provide, maintain, and improve our Services.</li>
              <li>Process and respond to your requests and inquiries.</li>
              <li>Personalize your experience on the platform.</li>
              <li>Train and improve our AI models (using anonymized and aggregated data only).</li>
              <li>Send administrative notifications and service updates.</li>
              <li>Detect, prevent, and address security issues and abuse.</li>
              <li>Comply with legal obligations.</li>
            </ul>
          </section>

          {/* 4 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">4. Data Storage</h2>
            <p className="leading-relaxed text-muted-foreground">
              Your data is stored on secure servers. We employ industry-standard encryption for sensitive
              data, including API credentials and access tokens, which are encrypted at rest using strong
              cryptographic algorithms. We retain your personal data only for as long as necessary to
              fulfill the purposes for which it was collected, or as required by law. You may request
              deletion of your data at any time by contacting us.
            </p>
          </section>

          {/* 5 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">5. Cookies</h2>
            <p className="leading-relaxed text-muted-foreground">
              We use cookies and similar tracking technologies to enhance your experience on our platform.
              Cookies help us:
            </p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li>Authenticate users and maintain session state.</li>
              <li>Remember your preferences and settings.</li>
              <li>Analyze usage patterns to improve the Services.</li>
            </ul>
            <p className="leading-relaxed text-muted-foreground mt-3">
              You can configure your browser to refuse cookies, though some features of the Services may
              not function properly without them.
            </p>
          </section>

          {/* 6 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">6. Third-Party Services</h2>
            <p className="leading-relaxed text-muted-foreground">
              Our Services may integrate with or link to third-party platforms and services, including
              but not limited to:
            </p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li>WhatsApp Business API (Meta Platforms)</li>
              <li>Facebook Graph API (Meta Platforms)</li>
              <li>AI/LLM providers for natural language processing</li>
            </ul>
            <p className="leading-relaxed text-muted-foreground mt-3">
              These third-party services have their own privacy policies. We encourage you to review the
              privacy practices of any third-party service before providing information to them. We are
              not responsible for the privacy practices of third-party services.
            </p>
          </section>

          {/* 7 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">7. Security</h2>
            <p className="leading-relaxed text-muted-foreground">
              We take the security of your data seriously and implement appropriate technical and
              organizational measures to protect it, including:
            </p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li>Encryption of sensitive data in transit (TLS) and at rest.</li>
              <li>Role-based access controls and authentication mechanisms.</li>
              <li>Regular security audits and monitoring.</li>
              <li>Secure infrastructure with firewalls and intrusion detection.</li>
            </ul>
            <p className="leading-relaxed text-muted-foreground mt-3">
              However, no method of electronic transmission or storage is 100% secure. While we strive
              to protect your information, we cannot guarantee absolute security.
            </p>
          </section>

          {/* 8 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">8. User Rights</h2>
            <p className="leading-relaxed text-muted-foreground">Depending on your jurisdiction, you may have the following rights:</p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li><strong className="text-foreground">Access:</strong> Request a copy of the personal data we hold about you.</li>
              <li><strong className="text-foreground">Correction:</strong> Request correction of inaccurate or incomplete data.</li>
              <li><strong className="text-foreground">Deletion:</strong> Request deletion of your personal data.</li>
              <li><strong className="text-foreground">Portability:</strong> Request your data in a structured, machine-readable format.</li>
              <li><strong className="text-foreground">Objection:</strong> Object to the processing of your data for certain purposes.</li>
            </ul>
            <p className="leading-relaxed text-muted-foreground mt-3">
              To exercise any of these rights, please contact us using the information provided below.
              We will respond to your request within a reasonable timeframe.
            </p>
          </section>

          {/* 9 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">9. Contact Information</h2>
            <p className="leading-relaxed text-muted-foreground">
              If you have any questions or concerns about this Privacy Policy, please contact us at:
            </p>
            <div className="mt-3 rounded-lg border p-4 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Fazle AI</p>
              <p>Email: contact@iamazim.com</p>
              <p>Website: https://iamazim.com</p>
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-12">
        <div className="mx-auto max-w-4xl px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} Fazle AI. All rights reserved.</p>
          <nav className="flex gap-4">
            <Link href="/terms-services" className="hover:text-foreground transition-colors">Terms of Service</Link>
            <Link href="/privacy-policy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
