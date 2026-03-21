import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Terms of Service – Fazle AI',
  description: 'Terms of Service for Fazle AI platform',
};

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-lg font-bold">Fazle AI</Link>
          <nav className="flex gap-4 text-sm">
            <Link href="/privacy-policy" className="text-muted-foreground hover:text-foreground transition-colors">Privacy Policy</Link>
            <Link href="/login" className="text-muted-foreground hover:text-foreground transition-colors">Login</Link>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Terms of Service</h1>
        <p className="text-sm text-muted-foreground mb-10">Last updated: March 21, 2026</p>

        <div className="prose prose-neutral dark:prose-invert max-w-none space-y-8">
          {/* 1 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">1. Introduction</h2>
            <p className="leading-relaxed text-muted-foreground">
              Welcome to Fazle AI (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;). These Terms of Service (&quot;Terms&quot;) govern your
              access to and use of the Fazle AI platform, including all related services, features, content,
              applications, and tools (collectively, the &quot;Services&quot;). By accessing or using our Services,
              you agree to be bound by these Terms.
            </p>
          </section>

          {/* 2 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">2. Acceptance of Terms</h2>
            <p className="leading-relaxed text-muted-foreground">
              By creating an account, accessing, or using the Services, you acknowledge that you have read,
              understood, and agree to be bound by these Terms. If you do not agree to these Terms, you may
              not access or use our Services. We reserve the right to modify these Terms at any time. Your
              continued use of the Services after any modifications constitutes your acceptance of the
              updated Terms.
            </p>
          </section>

          {/* 3 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">3. Use of Services</h2>
            <p className="leading-relaxed text-muted-foreground">You agree to use the Services only for lawful purposes and in accordance with these Terms. You may not:</p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li>Use the Services in any way that violates applicable laws or regulations.</li>
              <li>Attempt to gain unauthorized access to any part of the Services or related systems.</li>
              <li>Use the Services to transmit harmful, offensive, or illegal content.</li>
              <li>Interfere with or disrupt the integrity or performance of the Services.</li>
              <li>Reverse-engineer, decompile, or disassemble any aspect of the Services.</li>
              <li>Use automated tools to scrape, crawl, or extract data from the Services without authorization.</li>
            </ul>
          </section>

          {/* 4 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">4. User Responsibilities</h2>
            <p className="leading-relaxed text-muted-foreground">As a user of Fazle AI, you are responsible for:</p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li>Maintaining the confidentiality of your account credentials.</li>
              <li>All activities that occur under your account.</li>
              <li>Ensuring that your use of the Services complies with all applicable laws.</li>
              <li>The accuracy and legality of any data or content you provide to the platform.</li>
              <li>Promptly notifying us of any unauthorized use of your account.</li>
            </ul>
          </section>

          {/* 5 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">5. AI Usage Disclaimer</h2>
            <p className="leading-relaxed text-muted-foreground">
              Fazle AI utilizes artificial intelligence and machine learning technologies to provide its
              Services. While we strive for accuracy and reliability, AI-generated outputs may contain
              errors, inaccuracies, or biases. You acknowledge and agree that:
            </p>
            <ul className="list-disc pl-6 mt-3 space-y-2 text-muted-foreground">
              <li>AI-generated content should not be solely relied upon for critical decisions.</li>
              <li>We do not guarantee the accuracy, completeness, or reliability of AI-generated outputs.</li>
              <li>You are responsible for reviewing and verifying any AI-generated content before use.</li>
              <li>AI models may evolve over time, which may affect the consistency of outputs.</li>
            </ul>
          </section>

          {/* 6 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">6. Limitation of Liability</h2>
            <p className="leading-relaxed text-muted-foreground">
              To the maximum extent permitted by applicable law, Fazle AI and its affiliates, officers,
              directors, employees, and agents shall not be liable for any indirect, incidental, special,
              consequential, or punitive damages, including but not limited to loss of profits, data, use,
              goodwill, or other intangible losses, resulting from your access to or use of (or inability
              to access or use) the Services. Our total liability for any claim arising from or related to
              these Terms or the Services shall not exceed the amount you paid to us in the twelve months
              preceding the claim.
            </p>
          </section>

          {/* 7 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">7. Termination</h2>
            <p className="leading-relaxed text-muted-foreground">
              We may suspend or terminate your access to the Services at any time, with or without cause
              and with or without notice. Upon termination, your right to use the Services will immediately
              cease. You may also terminate your account at any time by contacting us. Any provisions of
              these Terms that by their nature should survive termination shall remain in effect.
            </p>
          </section>

          {/* 8 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">8. Changes to Terms</h2>
            <p className="leading-relaxed text-muted-foreground">
              We reserve the right to modify or replace these Terms at any time at our sole discretion.
              If a revision is material, we will provide at least 30 days&apos; notice prior to any new terms
              taking effect. What constitutes a material change will be determined at our sole discretion.
              By continuing to access or use our Services after those revisions become effective, you agree
              to be bound by the revised Terms.
            </p>
          </section>

          {/* 9 */}
          <section>
            <h2 className="text-xl font-semibold mb-3">9. Contact Information</h2>
            <p className="leading-relaxed text-muted-foreground">
              If you have any questions about these Terms of Service, please contact us at:
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
